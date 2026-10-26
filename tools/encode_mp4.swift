// Encodes a folder of same-sized PNG frames (sorted by name) into an H.264 MP4
// with the index at the front, so it can start playing while it downloads.
// Usage: swift tools/encode_mp4.swift <frames-dir> <out.mp4> [fps]
import AVFoundation
import CoreGraphics
import Foundation
import ImageIO

let args = CommandLine.arguments
guard args.count >= 3 else { print("usage: encode_mp4.swift <frames-dir> <out.mp4> [fps]"); exit(2) }
let framesDir = URL(fileURLWithPath: args[1])
let outURL = URL(fileURLWithPath: args[2])
let fps = Int32(args.count > 3 ? Int(args[3]) ?? 30 : 30)
let files = try FileManager.default.contentsOfDirectory(atPath: framesDir.path).filter { $0.hasSuffix(".png") }.sorted()
guard !files.isEmpty else { print("no frames in \(framesDir.path)"); exit(1) }

func load(_ name: String) -> CGImage {
    let source = CGImageSourceCreateWithURL(framesDir.appendingPathComponent(name) as CFURL, nil)!
    return CGImageSourceCreateImageAtIndex(source, 0, nil)!
}

let first = load(files[0])
let width = first.width, height = first.height
try? FileManager.default.removeItem(at: outURL)
let writer = try AVAssetWriter(outputURL: outURL, fileType: .mp4)
writer.shouldOptimizeForNetworkUse = true
let input = AVAssetWriterInput(mediaType: .video, outputSettings: [
    AVVideoCodecKey: AVVideoCodecType.h264,
    AVVideoWidthKey: width,
    AVVideoHeightKey: height,
    AVVideoCompressionPropertiesKey: [
        AVVideoAverageBitRateKey: 3_000_000,
        AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
    ],
])
input.expectsMediaDataInRealTime = false
let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: [
    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32ARGB,
    kCVPixelBufferWidthKey as String: width,
    kCVPixelBufferHeightKey as String: height,
])
writer.add(input)
writer.startWriting()
writer.startSession(atSourceTime: .zero)

for (index, name) in files.enumerated() {
    while !input.isReadyForMoreMediaData { Thread.sleep(forTimeInterval: 0.005) }
    var buffer: CVPixelBuffer?
    CVPixelBufferPoolCreatePixelBuffer(nil, adaptor.pixelBufferPool!, &buffer)
    guard let pixels = buffer else { print("could not allocate a frame buffer"); exit(1) }
    CVPixelBufferLockBaseAddress(pixels, [])
    let context = CGContext(
        data: CVPixelBufferGetBaseAddress(pixels), width: width, height: height, bitsPerComponent: 8,
        bytesPerRow: CVPixelBufferGetBytesPerRow(pixels), space: CGColorSpace(name: CGColorSpace.sRGB)!,
        bitmapInfo: CGImageAlphaInfo.noneSkipFirst.rawValue)!
    context.draw(load(name), in: CGRect(x: 0, y: 0, width: width, height: height))
    CVPixelBufferUnlockBaseAddress(pixels, [])
    adaptor.append(pixels, withPresentationTime: CMTime(value: CMTimeValue(index), timescale: fps))
}

input.markAsFinished()
let done = DispatchSemaphore(value: 0)
writer.finishWriting { done.signal() }
done.wait()
guard writer.status == .completed else { print("encoding failed: \(String(describing: writer.error))"); exit(1) }
print("wrote \(files.count) frames at \(fps) fps to \(outURL.path)")
