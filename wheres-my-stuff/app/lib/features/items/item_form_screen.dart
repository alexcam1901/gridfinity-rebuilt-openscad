import 'package:flutter/material.dart';

import '../../data/item_repository.dart';
import '../../data/location_repository.dart';
import '../../models/item.dart';
import '../../models/location.dart';

/// Pre-fill data forwarded from the ingest-photo Lambda (confirm screen).
class IngestResult {
  final String name;
  final List<String> tags;
  final String? ocrText;

  const IngestResult({required this.name, this.tags = const [], this.ocrText});
}

/// Full-screen form to add or edit an item.
class ItemFormScreen extends StatefulWidget {
  const ItemFormScreen({
    super.key,
    this.prefill,
    this.initialLocationId,
    this.existing,
  });

  final IngestResult? prefill;
  final String? initialLocationId;
  final Item? existing;

  @override
  State<ItemFormScreen> createState() => _ItemFormScreenState();
}

class _ItemFormScreenState extends State<ItemFormScreen> {
  final _itemRepo = ItemRepository();
  final _locRepo = LocationRepository();

  late final _nameCtrl =
      TextEditingController(text: widget.existing?.name ?? widget.prefill?.name ?? '');
  late final _qtyCtrl = TextEditingController(
      text: (widget.existing?.quantity ?? 1).toString());
  late final _tagsCtrl = TextEditingController(
      text: (widget.existing?.tags ?? widget.prefill?.tags ?? const []).join(', '));
  late final _gridCtrl =
      TextEditingController(text: widget.existing?.gridfinityRef ?? '');

  String? _locationId =
      widget.existing?.locationId ?? widget.initialLocationId;
  String _locationLabel = 'None';
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _refreshLocationLabel();
  }

  Future<void> _refreshLocationLabel() async {
    if (_locationId == null) {
      setState(() => _locationLabel = 'None');
      return;
    }
    final path = _locRepo.path(_locationId!);
    if (mounted) {
      setState(() => _locationLabel = path.map((l) => l.name).join(' > '));
    }
  }

  Future<void> _pickLocation() async {
    final picked = await Navigator.push<Location>(
      context,
      MaterialPageRoute(builder: (_) => const _LocationPickerScreen()),
    );
    if (picked != null) {
      _locationId = picked.id;
      _refreshLocationLabel();
    }
  }

  Future<void> _save() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) return;
    final qty = int.tryParse(_qtyCtrl.text.trim()) ?? 1;
    final tags = _tagsCtrl.text
        .split(',')
        .map((t) => t.trim())
        .where((t) => t.isNotEmpty)
        .toList();
    setState(() => _saving = true);
    if (widget.existing != null) {
      await _itemRepo.update(widget.existing!.id,
          name: name, quantity: qty, tags: tags,
          locationId: _locationId, gridfinityRef: _gridCtrl.text.trim());
    } else {
      await _itemRepo.create(
        name: name,
        quantity: qty,
        tags: tags,
        locationId: _locationId,
        ocrText: widget.prefill?.ocrText,
        gridfinityRef: _gridCtrl.text.trim().isEmpty ? null : _gridCtrl.text.trim(),
      );
    }
    if (mounted) Navigator.pop(context, true);
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _qtyCtrl.dispose();
    _tagsCtrl.dispose();
    _gridCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.existing == null ? 'Add item' : 'Edit item'),
        actions: [
          TextButton(
            onPressed: _saving ? null : _save,
            child: const Text('Save'),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (widget.prefill?.ocrText != null && widget.prefill!.ocrText!.isNotEmpty) ...[
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Read from label',
                        style: Theme.of(context).textTheme.labelSmall),
                    const SizedBox(height: 4),
                    Text(widget.prefill!.ocrText!,
                        style: const TextStyle(fontFamily: 'monospace')),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
          ],
          TextField(
            controller: _nameCtrl,
            decoration: const InputDecoration(
              labelText: 'Name *',
              border: OutlineInputBorder(),
            ),
            textCapitalization: TextCapitalization.words,
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _qtyCtrl,
            decoration: const InputDecoration(
              labelText: 'Quantity',
              border: OutlineInputBorder(),
            ),
            keyboardType: TextInputType.number,
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _tagsCtrl,
            decoration: const InputDecoration(
              labelText: 'Tags (comma-separated)',
              hintText: 'electrical, connectors',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Location'),
            subtitle: Text(_locationLabel),
            trailing: const Icon(Icons.chevron_right),
            onTap: _pickLocation,
          ),
          const Divider(),
          TextField(
            controller: _gridCtrl,
            decoration: const InputDecoration(
              labelText: 'Gridfinity bin ref (optional)',
              hintText: 'e.g. 3x2-bin',
              border: OutlineInputBorder(),
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Simple location picker — browse tree, tap a leaf/node to select.
// ---------------------------------------------------------------------------

class _LocationPickerScreen extends StatefulWidget {
  const _LocationPickerScreen({this.parentId});

  final String? parentId;

  @override
  State<_LocationPickerScreen> createState() => _LocationPickerScreenState();
}

class _LocationPickerScreenState extends State<_LocationPickerScreen> {
  final _repo = LocationRepository();
  List<Location> _locs = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final locs = widget.parentId == null
        ? await _repo.listRoots()
        : await _repo.listChildren(widget.parentId!);
    if (mounted) setState(() => _locs = locs);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Pick location')),
      body: _locs.isEmpty
          ? const Center(child: Text('No locations here'))
          : ListView.builder(
              itemCount: _locs.length,
              itemBuilder: (_, i) {
                final loc = _locs[i];
                return ListTile(
                  title: Text(loc.name),
                  subtitle: Text(loc.type),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () async {
                    final children = await _repo.listChildren(loc.id);
                    if (!mounted) return;
                    if (children.isEmpty) {
                      Navigator.pop(context, loc);
                    } else {
                      final picked = await Navigator.push<Location>(
                        context,
                        MaterialPageRoute(
                          builder: (_) =>
                              _LocationPickerScreen(parentId: loc.id),
                        ),
                      );
                      if (picked != null && mounted) {
                        Navigator.pop(context, picked);
                      }
                    }
                  },
                  onLongPress: () => Navigator.pop(context, loc),
                );
              },
            ),
    );
  }
}
