import 'package:flutter/material.dart';

/// Capture flow: take/pick a photo, upload to S3, the `ingest-photo` Lambda
/// identifies it (Claude Haiku), then a confirm screen pre-fills name + tags for
/// a quick "looks right? save" into a location/bin. Camera + upload wiring is a
/// TODO until the backend is deployed.
class CaptureScreen extends StatelessWidget {
  const CaptureScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Add an item')),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.add_a_photo, size: 64),
            const SizedBox(height: 16),
            const Text('Snap a photo to catalog an item'),
            const SizedBox(height: 16),
            FilledButton.icon(
              icon: const Icon(Icons.camera_alt),
              label: const Text('Take photo'),
              // TODO: camera capture -> Amplify Storage upload ->
              // ingest-photo Lambda -> confirm screen pre-fill.
              onPressed: () {},
            ),
          ],
        ),
      ),
    );
  }
}
