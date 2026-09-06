import ReplayKit
import SwiftUI

/// Spike shell: its only job is to start the screen broadcast and tell the tester what to do.
/// Measurements come out of the extension through the unified log, not through this screen.
struct ContentView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            VStack(alignment: .leading, spacing: 6) {
                Text("DokkanScan")
                    .font(.largeTitle.bold())
                Text("Live capture spike")
                    .font(.headline)
                    .foregroundStyle(.secondary)
            }

            VStack(alignment: .leading, spacing: 12) {
                Step(number: 1, text: "In Dokkan, open the character list and sort it by rate.")
                Step(number: 2, text: "Tap the button below, then Start Broadcast.")
                Step(number: 3, text: "Switch to Dokkan and scroll through your box.")
                Step(number: 4, text: "Stop from the red status bar, then come back here.")
            }

            BroadcastButton()
                .frame(height: 64)

            Text("Frames are measured and discarded. Nothing is saved or uploaded.")
                .font(.footnote)
                .foregroundStyle(.secondary)

            Spacer()
        }
        .padding(28)
    }
}

private struct Step: View {
    let number: Int
    let text: String

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Text("\(number)")
                .font(.caption.bold().monospacedDigit())
                .frame(width: 22, height: 22)
                .background(Circle().fill(.tint.opacity(0.15)))
            Text(text)
        }
    }
}

/// The system picker is the only supported way to start a broadcast to our own extension.
private struct BroadcastButton: UIViewRepresentable {
    func makeUIView(context: Context) -> RPSystemBroadcastPickerView {
        let picker = RPSystemBroadcastPickerView(frame: CGRect(x: 0, y: 0, width: 200, height: 64))
        picker.preferredExtension = "io.keyban.dokkanscan.broadcast"
        picker.showsMicrophoneButton = false
        return picker
    }

    func updateUIView(_ view: RPSystemBroadcastPickerView, context: Context) {}
}
