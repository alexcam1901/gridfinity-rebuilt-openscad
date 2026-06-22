import 'package:flutter/material.dart';

import '../../data/item_repository.dart';
import '../../data/location_repository.dart';
import '../../models/item.dart';
import 'item_form_screen.dart';

class ItemDetailScreen extends StatefulWidget {
  const ItemDetailScreen({super.key, required this.item});

  final Item item;

  @override
  State<ItemDetailScreen> createState() => _ItemDetailScreenState();
}

class _ItemDetailScreenState extends State<ItemDetailScreen> {
  final _locRepo = LocationRepository();
  final _itemRepo = ItemRepository();
  late Item _item = widget.item;
  String _locationLabel = '';

  @override
  void initState() {
    super.initState();
    _refreshLocation();
  }

  Future<void> _refreshLocation() async {
    if (_item.locationId == null) return;
    final path = _locRepo.path(_item.locationId!);
    if (mounted) setState(() => _locationLabel = path.map((l) => l.name).join(' > '));
  }

  Future<void> _edit() async {
    final updated = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => ItemFormScreen(existing: _item)),
    );
    if (updated == true) {
      final refreshed = await _itemRepo.findById(_item.id);
      if (refreshed != null && mounted) {
        setState(() => _item = refreshed);
        _refreshLocation();
      }
    }
  }

  Future<void> _delete() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete item?'),
        content: Text('Remove "${_item.name}" from your inventory?'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Delete')),
        ],
      ),
    );
    if (confirmed == true) {
      await _itemRepo.delete(_item.id);
      if (mounted) Navigator.pop(context, true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_item.name),
        actions: [
          IconButton(icon: const Icon(Icons.edit), onPressed: _edit),
          IconButton(icon: const Icon(Icons.delete_outline), onPressed: _delete),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _InfoRow(label: 'Location', value: _locationLabel.isEmpty ? '—' : _locationLabel),
          _InfoRow(label: 'Quantity', value: _item.quantity.toString()),
          if (_item.tags.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Wrap(
                spacing: 8,
                children: _item.tags.map((t) => Chip(label: Text(t))).toList(),
              ),
            ),
          if (_item.ocrText != null && _item.ocrText!.isNotEmpty)
            _InfoRow(label: 'Label text', value: _item.ocrText!),
          if (_item.gridfinityRef != null && _item.gridfinityRef!.isNotEmpty)
            _InfoRow(label: 'Gridfinity bin', value: _item.gridfinityRef!),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 110,
            child: Text(label,
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: Theme.of(context).colorScheme.outline)),
          ),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }
}
