import 'package:flutter/material.dart';

import '../items/item_form_screen.dart';
import 'confirm_screen.dart';

/// Capture flow: take/pick a photo, upload to S3, the `ingest-photo` Lambda
/// identifies it (Claude Haiku), then a confirm screen pre-fills name + tags
/// for a quick "looks right? save" tap. Camera + Amplify wiring is a TODO
/// until the backend is deployed.
class CaptureScreen extends StatelessWidget {
  const CaptureScreen({super.key});

  void _simulateCapture(BuildContext context) {
    // TODO: replace with real camera capture -> Amplify Storage.putFile() ->
    // AppSync mutation `ingestPhoto(s3Key:)` -> Lambda returns IngestResult.
    // For now, simulate a Haiku response for a demo item.
    const demo = IngestResult(
      name: 'Wire nuts',
      tags: ['electrical', 'connectors'],
      ocrText: 'WIRE CONNECTORS 100 PACK',
    );
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const ConfirmScreen(result: demo)),
    );
  }

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
            const Text('Snap a photo — Claude identifies it for you'),
            const SizedBox(height: 24),
            FilledButton.icon(
              icon: const Icon(Icons.camera_alt),
              label: const Text('Take photo'),
              onPressed: () => _simulateCapture(context),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              icon: const Icon(Icons.add_box_outlined),
              label: const Text('Add manually'),
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const ItemFormScreen()),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
