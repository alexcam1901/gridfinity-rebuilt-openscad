import 'package:flutter/material.dart';

import '../items/item_form_screen.dart';

/// Receives the structured result from the ingest-photo Lambda (Claude Haiku)
/// and lets the user accept, edit, and assign a location before saving.
class ConfirmScreen extends StatelessWidget {
  const ConfirmScreen({super.key, required this.result});

  final IngestResult result;

  @override
  Widget build(BuildContext context) {
    // Delegate immediately to ItemFormScreen with the pre-filled data.
    return ItemFormScreen(prefill: result);
  }
}
