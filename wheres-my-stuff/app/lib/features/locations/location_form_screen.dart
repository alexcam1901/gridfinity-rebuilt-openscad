import 'package:flutter/material.dart';

import '../../data/location_repository.dart';
import '../../models/location.dart';

/// Shows a bottom sheet to create or edit a [Location].
/// Returns the saved [Location] or null if cancelled.
Future<Location?> showLocationForm(
  BuildContext context, {
  String? parentId,
  Location? existing,
}) async {
  return showModalBottomSheet<Location>(
    context: context,
    isScrollControlled: true,
    builder: (_) => _LocationForm(parentId: parentId, existing: existing),
  );
}

class _LocationForm extends StatefulWidget {
  const _LocationForm({this.parentId, this.existing});

  final String? parentId;
  final Location? existing;

  @override
  State<_LocationForm> createState() => _LocationFormState();
}

class _LocationFormState extends State<_LocationForm> {
  final _repo = LocationRepository();
  late final _nameCtrl = TextEditingController(text: widget.existing?.name ?? '');
  late final _notesCtrl = TextEditingController(text: widget.existing?.notes ?? '');
  late String _type = widget.existing?.type ?? 'other';
  bool _saving = false;

  Future<void> _save() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) return;
    setState(() => _saving = true);
    Location result;
    if (widget.existing != null) {
      await _repo.update(widget.existing!.id,
          name: name, type: _type, notes: _notesCtrl.text.trim());
      result = widget.existing!
          .copyWith(name: name, type: _type, notes: _notesCtrl.text.trim());
    } else {
      result = await _repo.create(
        name: name,
        type: _type,
        parentId: widget.parentId,
        notes: _notesCtrl.text.trim(),
      );
    }
    if (mounted) Navigator.pop(context, result);
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _notesCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(24, 24, 24, 24 + bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            widget.existing == null ? 'Add location' : 'Edit location',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _nameCtrl,
            autofocus: true,
            decoration: const InputDecoration(
              labelText: 'Name',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            value: _type,
            decoration: const InputDecoration(
              labelText: 'Type',
              border: OutlineInputBorder(),
            ),
            items: Location.types
                .map((t) => DropdownMenuItem(value: t, child: Text(t)))
                .toList(),
            onChanged: (v) => setState(() => _type = v ?? _type),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _notesCtrl,
            decoration: const InputDecoration(
              labelText: 'Notes (optional)',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 20),
          FilledButton(
            onPressed: _saving ? null : _save,
            child: _saving ? const CircularProgressIndicator() : const Text('Save'),
          ),
        ],
      ),
    );
  }
}
