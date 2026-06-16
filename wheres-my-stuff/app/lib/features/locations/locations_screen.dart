import 'package:flutter/material.dart';

import '../../data/location_repository.dart';
import '../../models/location.dart';
import 'location_detail_screen.dart';
import 'location_form_screen.dart';

class LocationsScreen extends StatefulWidget {
  const LocationsScreen({super.key});

  @override
  State<LocationsScreen> createState() => _LocationsScreenState();
}

class _LocationsScreenState extends State<LocationsScreen> {
  final _repo = LocationRepository();
  List<Location> _roots = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final roots = await _repo.listRoots();
    if (mounted) setState(() => _roots = roots);
  }

  Future<void> _addRoot() async {
    final loc = await showLocationForm(context, parentId: null);
    if (loc != null) _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Browse')),
      floatingActionButton: FloatingActionButton(
        onPressed: _addRoot,
        tooltip: 'Add room / area',
        child: const Icon(Icons.add),
      ),
      body: _roots.isEmpty
          ? const Center(
              child: Text('No locations yet.\nTap + to add a room or area.',
                  textAlign: TextAlign.center),
            )
          : ListView.builder(
              itemCount: _roots.length,
              itemBuilder: (_, i) => _LocationTile(
                location: _roots[i],
                onChanged: _load,
              ),
            ),
    );
  }
}

class _LocationTile extends StatelessWidget {
  const _LocationTile({required this.location, required this.onChanged});

  final Location location;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(_iconFor(location.type)),
      title: Text(location.name),
      subtitle: Text(location.type),
      trailing: const Icon(Icons.chevron_right),
      onTap: () async {
        await Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) =>
                LocationDetailScreen(location: location),
          ),
        );
        onChanged();
      },
    );
  }

  IconData _iconFor(String type) => switch (type) {
        'room' => Icons.home,
        'shelf' => Icons.shelves,
        'cabinet' => Icons.door_sliding,
        'drawer' => Icons.dns,
        'bin' => Icons.inbox,
        _ => Icons.place,
      };
}
