// Stage 0A candidate visual labels using the macOS built-in Vision framework
// (no downloaded models). Reads image paths from stdin, writes one JSON object
// per line: faces, human bodies, cat/dog, scene classification, recognized text.
// All outputs are CANDIDATES for Stage 0B review, not visual facts.
import Foundation
import Vision
import ImageIO

func box(_ r: CGRect) -> [Double] { [r.minX, 1 - r.maxY, r.width, r.height].map { (Double($0) * 1000).rounded() / 1000 } }

let enc = JSONSerialization.self
while let line = readLine() {
    let path = line.trimmingCharacters(in: .whitespaces)
    if path.isEmpty { continue }
    var out: [String: Any] = ["path": path]
    guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
          let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
        out["error"] = "unreadable"
        print(String(data: try! enc.data(withJSONObject: out), encoding: .utf8)!)
        continue
    }
    let faces = VNDetectFaceRectanglesRequest()
    let humans = VNDetectHumanRectanglesRequest()
    humans.upperBodyOnly = false
    let animals = VNRecognizeAnimalsRequest()
    let classify = VNClassifyImageRequest()
    let text = VNRecognizeTextRequest()
    text.recognitionLevel = .accurate
    text.recognitionLanguages = ["zh-Hant", "zh-Hans", "ja-JP", "en-US"]
    text.usesLanguageCorrection = true
    let handler = VNImageRequestHandler(cgImage: img, options: [:])
    do {
        try handler.perform([faces, humans, animals, classify, text])
    } catch {
        out["error"] = "\(error)"
    }
    out["faces"] = (faces.results ?? []).map { ["box": box($0.boundingBox), "conf": Double($0.confidence)] }
    out["humans"] = (humans.results ?? []).map { ["box": box($0.boundingBox), "conf": Double($0.confidence)] }
    out["animals"] = (animals.results ?? []).map { o -> [String: Any] in
        ["box": box(o.boundingBox), "labels": o.labels.map { ["id": $0.identifier, "conf": Double($0.confidence)] }]
    }
    out["classes"] = (classify.results ?? []).filter { $0.confidence >= 0.15 }.prefix(10)
        .map { ["id": $0.identifier, "conf": (Double($0.confidence) * 1000).rounded() / 1000] }
    out["text"] = (text.results ?? []).compactMap { o -> [String: Any]? in
        guard let c = o.topCandidates(1).first, c.confidence >= 0.3 else { return nil }
        return ["text": c.string, "conf": Double(c.confidence), "box": box(o.boundingBox)]
    }
    print(String(data: try! enc.data(withJSONObject: out), encoding: .utf8)!)
    fflush(stdout)
}
