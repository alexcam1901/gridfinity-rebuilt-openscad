import '../models/location.dart';
import 'mock_db.dart';

class LocationRepository {
  final _db = MockDb.instance;

  Future<List<Location>> listRoots() async =>
      _db.locations.where((l) => l.parentId == null).toList();

  Future<List<Location>> listChildren(String parentId) async =>
      _db.locations.where((l) => l.parentId == parentId).toList();

  Future<Location?> findById(String id) async =>
      _db.locations.where((l) => l.id == id).firstOrNull;

  Future<Location> create({
    required String name,
    required String type,
    String? parentId,
    String? notes,
  }) async {
    final loc = Location(
      id: _db.nextLocId(),
      name: name,
      type: type,
      parentId: parentId,
      notes: notes,
    );
    _db.locations.add(loc);
    return loc;
  }

  Future<void> update(String id, {String? name, String? type, String? notes}) async {
    final i = _db.locations.indexWhere((l) => l.id == id);
    if (i < 0) return;
    _db.locations[i] = _db.locations[i].copyWith(
      name: name,
      type: type,
      notes: notes,
    );
  }

  Future<void> delete(String id) async {
    _db.locations.removeWhere((l) => l.id == id);
  }

  /// Full location path as a list from root to the given id.
  List<Location> path(String locationId) =>
      _db.ancestors(locationId).reversed.toList();
}
