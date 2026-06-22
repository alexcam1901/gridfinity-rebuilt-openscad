import '../models/item.dart';
import '../models/location.dart';

/// In-memory database shared by all repositories.
///
/// Seeded with a realistic garage/house inventory so every screen works
/// end-to-end without a backend connection. Swap repository implementations
/// for Amplify AppSync calls once `ampx sandbox` is running.
class MockDb {
  static final MockDb instance = MockDb._();
  MockDb._() {
    _seed();
  }

  final List<Location> locations = [];
  final List<Item> items = [];

  int _locSeq = 100;
  int _itemSeq = 100;

  String nextLocId() => 'loc_${++_locSeq}';
  String nextItemId() => 'item_${++_itemSeq}';

  void _seed() {
    // Garage hierarchy
    const garage = Location(id: 'garage', name: 'Garage', type: 'room');
    const shelfA = Location(id: 'shelfA', name: 'Wall shelf A', type: 'shelf', parentId: 'garage');
    const shelfABin1 = Location(id: 'shelfA_bin1', name: 'Bin 1', type: 'bin', parentId: 'shelfA');
    const shelfABin2 = Location(id: 'shelfA_bin2', name: 'Bin 2', type: 'bin', parentId: 'shelfA');
    const shelfABin3 = Location(id: 'shelfA_bin3', name: 'Bin 3', type: 'bin', parentId: 'shelfA');
    const shelfB = Location(id: 'shelfB', name: 'Wall shelf B', type: 'shelf', parentId: 'garage');
    const shelfBBin1 = Location(id: 'shelfB_bin1', name: 'Bin 1', type: 'bin', parentId: 'shelfB');
    const shelfBBin2 = Location(id: 'shelfB_bin2', name: 'Bin 2', type: 'bin', parentId: 'shelfB');
    const bench = Location(id: 'bench', name: 'Tool bench', type: 'cabinet', parentId: 'garage');

    // Kitchen hierarchy
    const kitchen = Location(id: 'kitchen', name: 'Kitchen', type: 'room');
    const junkDrawer = Location(id: 'junk_drawer', name: 'Junk drawer', type: 'drawer', parentId: 'kitchen');

    // Basement hierarchy
    const basement = Location(id: 'basement', name: 'Basement', type: 'room');
    const storageSh = Location(id: 'storage_shelf', name: 'Storage shelf', type: 'shelf', parentId: 'basement');

    locations.addAll([
      garage, shelfA, shelfABin1, shelfABin2, shelfABin3,
      shelfB, shelfBBin1, shelfBBin2, bench,
      kitchen, junkDrawer,
      basement, storageSh,
    ]);

    items.addAll([
      const Item(id: 'i1', name: 'Wire nuts', quantity: 100,
          tags: ['electrical', 'connectors'], ocrText: 'WIRE CONNECTORS 100 PACK',
          locationId: 'shelfA_bin1'),
      const Item(id: 'i2', name: 'Zip ties', quantity: 200,
          tags: ['cable', 'fasteners', 'black'], ocrText: 'CABLE TIES 8 IN',
          locationId: 'shelfA_bin2'),
      const Item(id: 'i3', name: 'Electrical tape', quantity: 5,
          tags: ['electrical', 'insulation'], ocrText: 'ELECTRICAL TAPE SCOTCH',
          locationId: 'shelfA_bin3'),
      const Item(id: 'i4', name: 'Drill bits', quantity: 20,
          tags: ['tools', 'metal', 'drill'], ocrText: 'COBALT DRILL BIT SET',
          locationId: 'shelfB_bin1'),
      const Item(id: 'i5', name: 'Wood screws assorted', quantity: 500,
          tags: ['fasteners', 'wood', 'screws'], ocrText: 'WOOD SCREWS ASSORTED',
          locationId: 'shelfB_bin2'),
      const Item(id: 'i6', name: 'Cordless drill', quantity: 1,
          tags: ['power tool', '20v', 'dewalt'], ocrText: 'DEWALT 20V MAX',
          locationId: 'bench'),
      const Item(id: 'i7', name: 'Level 24in', quantity: 1,
          tags: ['measurement', 'tools'], ocrText: '',
          locationId: 'bench'),
      const Item(id: 'i8', name: 'AA batteries', quantity: 24,
          tags: ['batteries', 'electrical', 'alkaline'], ocrText: 'DURACELL AA 20 PACK',
          locationId: 'junk_drawer'),
      const Item(id: 'i9', name: 'Tape measure 25ft', quantity: 1,
          tags: ['measurement', 'tools'], ocrText: 'STANLEY TAPE MEASURE',
          locationId: 'junk_drawer'),
      const Item(id: 'i10', name: 'Extension cord 25ft', quantity: 2,
          tags: ['electrical', 'power', 'orange'], ocrText: 'EXTENSION CORD 25 FT 16 AWG',
          locationId: 'storage_shelf'),
      const Item(id: 'i11', name: 'Duct tape', quantity: 3,
          tags: ['fasteners', 'general', 'gray'], ocrText: 'DUCK TAPE',
          locationId: 'storage_shelf'),
    ]);
  }

  /// Full ancestor chain for a location, closest first, root last.
  List<Location> ancestors(String locationId) {
    final result = <Location>[];
    String? cur = locationId;
    final seen = <String>{};
    while (cur != null && !seen.contains(cur)) {
      seen.add(cur);
      final loc = locations.firstWhere((l) => l.id == cur,
          orElse: () => const Location(id: '', name: '', type: ''));
      if (loc.id.isEmpty) break;
      result.add(loc);
      cur = loc.parentId;
    }
    return result;
  }

  /// "Garage > Wall shelf A > Bin 1" style breadcrumb for a locationId.
  String breadcrumb(String? locationId) {
    if (locationId == null) return '';
    return ancestors(locationId).reversed.map((l) => l.name).join(' > ');
  }
}
