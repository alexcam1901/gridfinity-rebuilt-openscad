import 'package:flutter/material.dart';

import '../../data/item_repository.dart';
import '../../data/location_repository.dart';
import '../../models/item.dart';
import '../../models/location.dart';
import '../items/item_detail_screen.dart';
import '../items/item_form_screen.dart';
import 'location_form_screen.dart';

class LocationDetailScreen extends StatefulWidget {
  const LocationDetailScreen({super.key, required this.location});

  final Location location;

  @override
  State<LocationDetailScreen> createState() => _LocationDetailScreenState();
}

class _LocationDetailScreenState extends State<LocationDetailScreen> {
  final _locRepo = LocationRepository();
  final _itemRepo = ItemRepository();
  late Location _location = widget.location;

  List<Location> _children = const [];
  List<Item> _items = const [];
  List<Location> _breadcrumb = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final children = await _locRepo.listChildren(_location.id);
    final items = await _itemRepo.listByLocation(_location.id);
    final path = _locRepo.path(_location.id);
    if (mounted) {
      setState(() {
        _children = children;
        _items = items;
        _breadcrumb = path;
      });
    }
  }

  Future<void> _addChild() async {
    final loc = await showLocationForm(context, parentId: _location.id);
    if (loc != null) _load();
  }

  Future<void> _addItem() async {
    final added = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => ItemFormScreen(initialLocationId: _location.id),
      ),
    );
    if (added == true) _load();
  }

  Future<void> _editLocation() async {
    final updated = await showLocationForm(context, existing: _location);
    if (updated != null) {
      setState(() => _location = updated);
    }
  }

  Future<void> _deleteLocation() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete location?'),
        content: Text('Remove "${_location.name}"? Items inside are not deleted.'),
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
      await _locRepo.delete(_location.id);
      if (mounted) Navigator.pop(context, true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_location.name),
        actions: [
          IconButton(icon: const Icon(Icons.edit), onPressed: _editLocation),
          IconButton(
              icon: const Icon(Icons.delete_outline), onPressed: _deleteLocation),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _addItem,
        icon: const Icon(Icons.add),
        label: const Text('Add item'),
      ),
      body: CustomScrollView(
        slivers: [
          if (_breadcrumb.length > 1)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                child: Text(
                  _breadcrumb.map((l) => l.name).join(' > '),
                  style: Theme.of(context)
                      .textTheme
                      .bodySmall
                      ?.copyWith(color: Theme.of(context).colorScheme.outline),
                ),
              ),
            ),
          if (_children.isNotEmpty) ...[
            _sectionHeader(context, 'Sub-locations',
                trailing: TextButton.icon(
                  icon: const Icon(Icons.add, size: 16),
                  label: const Text('Add'),
                  onPressed: _addChild,
                )),
            SliverList(
              delegate: SliverChildBuilderDelegate(
                (_, i) => _ChildLocTile(
                    location: _children[i], onChanged: _load),
                childCount: _children.length,
              ),
            ),
          ] else
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                child: OutlinedButton.icon(
                  icon: const Icon(Icons.create_new_folder),
                  label: const Text('Add sub-location'),
                  onPressed: _addChild,
                ),
              ),
            ),
          _sectionHeader(context, 'Items (${_items.length})'),
          if (_items.isEmpty)
            const SliverToBoxAdapter(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Text('No items here yet.'),
              ),
            )
          else
            SliverList(
              delegate: SliverChildBuilderDelegate(
                (_, i) => _ItemTile(item: _items[i], onChanged: _load),
                childCount: _items.length,
              ),
            ),
          const SliverToBoxAdapter(child: SizedBox(height: 80)),
        ],
      ),
    );
  }

  SliverToBoxAdapter _sectionHeader(BuildContext context, String title,
      {Widget? trailing}) {
    return SliverToBoxAdapter(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 8, 4),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(title,
                style: Theme.of(context)
                    .textTheme
                    .titleSmall
                    ?.copyWith(color: Theme.of(context).colorScheme.primary)),
            if (trailing != null) trailing,
          ],
        ),
      ),
    );
  }
}

class _ChildLocTile extends StatelessWidget {
  const _ChildLocTile({required this.location, required this.onChanged});

  final Location location;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: const Icon(Icons.folder_outlined),
      title: Text(location.name),
      subtitle: Text(location.type),
      trailing: const Icon(Icons.chevron_right),
      onTap: () async {
        await Navigator.push(
          context,
          MaterialPageRoute(
              builder: (_) => LocationDetailScreen(location: location)),
        );
        onChanged();
      },
    );
  }
}

class _ItemTile extends StatelessWidget {
  const _ItemTile({required this.item, required this.onChanged});

  final Item item;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text(item.name),
      subtitle:
          item.tags.isEmpty ? null : Text(item.tags.take(3).join(', ')),
      trailing: Text('×${item.quantity}',
          style: Theme.of(context).textTheme.bodySmall),
      onTap: () async {
        await Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => ItemDetailScreen(item: item)),
        );
        onChanged();
      },
    );
  }
}
