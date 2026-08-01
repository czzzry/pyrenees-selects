import Foundation
import ImageIO
import Vision

enum LandmarkError: Error, CustomStringConvertible {
    case noArguments
    case noFace(String)
    case missingEyes(String)

    var description: String {
        switch self {
        case .noArguments:
            return "Pass at least one image path."
        case .noFace(let path):
            return "No face was detected in \(path)."
        case .missingEyes(let path):
            return "Both eyes were not detected in \(path)."
        }
    }
}

func exifOrientation(for url: URL) -> CGImagePropertyOrientation {
    guard
        let source = CGImageSourceCreateWithURL(url as CFURL, nil),
        let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any],
        let raw = properties[kCGImagePropertyOrientation] as? NSNumber,
        let orientation = CGImagePropertyOrientation(rawValue: raw.uint32Value)
    else {
        return .up
    }
    return orientation
}

func analysisImage(for url: URL, maxPixelSize: Int = 1600) throws -> CGImage {
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil) else {
        throw CocoaError(.fileReadCorruptFile)
    }
    let options: [CFString: Any] = [
        kCGImageSourceCreateThumbnailFromImageAlways: true,
        kCGImageSourceCreateThumbnailWithTransform: true,
        kCGImageSourceThumbnailMaxPixelSize: maxPixelSize,
        kCGImageSourceShouldCacheImmediately: true,
    ]
    guard let image = CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary) else {
        throw CocoaError(.fileReadCorruptFile)
    }
    return image
}

func center(of region: VNFaceLandmarkRegion2D?, in face: VNFaceObservation) -> [String: Double]? {
    guard let region, region.pointCount > 0 else {
        return nil
    }
    let points = region.normalizedPoints
    let sum = points.reduce(CGPoint.zero) { partial, point in
        CGPoint(x: partial.x + point.x, y: partial.y + point.y)
    }
    let local = CGPoint(
        x: sum.x / CGFloat(points.count),
        y: sum.y / CGFloat(points.count)
    )
    let box = face.boundingBox
    let imageX = box.minX + local.x * box.width
    let imageYFromBottom = box.minY + local.y * box.height
    return [
        "x": Double(imageX),
        "y": Double(1.0 - imageYFromBottom),
    ]
}

func analyze(path: String) throws -> [String: Any] {
    let url = URL(fileURLWithPath: path)
    let orientation = exifOrientation(for: url)
    let image = try analysisImage(for: url)
    let request = VNDetectFaceLandmarksRequest()
    let qualityRequest = VNDetectFaceCaptureQualityRequest()
    let handler = VNImageRequestHandler(cgImage: image, orientation: .up, options: [:])
    try handler.perform([request, qualityRequest])

    guard let face = request.results?
        .max(by: { lhs, rhs in
            lhs.boundingBox.width * lhs.boundingBox.height <
                rhs.boundingBox.width * rhs.boundingBox.height
        })
    else {
        throw LandmarkError.noFace(path)
    }
    guard
        let leftEye = center(of: face.landmarks?.leftEye, in: face),
        let rightEye = center(of: face.landmarks?.rightEye, in: face)
    else {
        throw LandmarkError.missingEyes(path)
    }

    let box = face.boundingBox
    var result: [String: Any] = [
        "path": url.path,
        "filename": url.lastPathComponent,
        "orientation": orientation.rawValue,
        "analysis_width": image.width,
        "analysis_height": image.height,
        "face_confidence": Double(face.confidence),
        "face_box": [
            "x": Double(box.minX),
            "y": Double(1.0 - box.maxY),
            "width": Double(box.width),
            "height": Double(box.height),
        ],
        "left_eye": leftEye,
        "right_eye": rightEye,
    ]
    let qualityFace = qualityRequest.results?
        .max(by: { lhs, rhs in
            lhs.boundingBox.width * lhs.boundingBox.height <
                rhs.boundingBox.width * rhs.boundingBox.height
        })
    if let faceQuality = qualityFace?.faceCaptureQuality {
        result["face_capture_quality"] = faceQuality
    }
    if let landmarks = face.landmarks {
        result["landmark_confidence"] = Double(landmarks.confidence)
    }
    return result
}

let arguments = Array(CommandLine.arguments.dropFirst())
guard !arguments.isEmpty else {
    FileHandle.standardError.write(Data("\(LandmarkError.noArguments)\n".utf8))
    exit(2)
}

var results: [[String: Any]] = []
var failures: [[String: String]] = []
for (index, path) in arguments.enumerated() {
    do {
        results.append(try analyze(path: path))
    } catch {
        failures.append([
            "path": path,
            "filename": URL(fileURLWithPath: path).lastPathComponent,
            "error": String(describing: error),
        ])
    }
    let completed = index + 1
    if completed % 10 == 0 || completed == arguments.count || failures.last?["path"] == path {
        let status = failures.last?["path"] == path ? "exception" : "ok"
        FileHandle.standardError.write(
            Data("[Vision \(completed)/\(arguments.count)] \(URL(fileURLWithPath: path).lastPathComponent) · \(status)\n".utf8)
        )
    }
}

let payload: [String: Any] = [
    "results": results,
    "failures": failures,
]
let data = try JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted, .sortedKeys])
FileHandle.standardOutput.write(data)
FileHandle.standardOutput.write(Data("\n".utf8))
