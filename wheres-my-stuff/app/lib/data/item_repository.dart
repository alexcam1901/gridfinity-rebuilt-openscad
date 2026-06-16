import '../models/item.dart';
import 'mock_db.dart';

class ItemRepository {
  final _db = MockDb.instance;

  Future<List<Item>> listByLocation(String locationId) async =>
      _db.items.where((it) => it.locationId == locationId).toList();

  Future<Item?> findById(String id) async =>
      _db.items.where((it) => it.id == id).firstOrNull;

  Future<Item> create({
    required String name,
    int quantity = 1,
    List<String> tags = const [],
    String? locationId,
    String? ocrText,
    String? gridfinityRef,
  }) async {
    final item = Item(
      id: _db.nextItemId(),
      name: name,
      quantity: quantity,
      tags: tags,
      locationId: locationId,
      ocrText: ocrText,
      gridfinityRef: gridfinityRef,
    );
    _db.items.add(item);
    return item;
  }

  Future<void> update(
    String id, {
    String? name,
    int? quantity,
    List<String>? tags,
    String? locationId,
    String? ocrText,
    String? gridfinityRef,
  }) async {
    final i = _db.items.indexWhere((it) => it.id == id);
    if (i < 0) return;
    _db.items[i] = _db.items[i].copyWith(
      name: name,
      quantity: quantity,
      tags: tags,
      locationId: locationId,
      ocrText: ocrText,
      gridfinityRef: gridfinityRef,
    );
  }

  Future<void> delete(String id) async {
    _db.items.removeWhere((it) => it.id == id);
  }

  /// Synonym-aware ranked search across name, tags, and OCR text.
  /// Mirrors the Python `rank_matches` logic in backend/functions/query/handler.py.
  Future<List<({String id, String name, String location, int? quantity})>> search(
    String query,
  ) async {
    final db = _db;
    if (query.trim().isEmpty) return const [];

    final terms = _queryTerms(query);
    if (terms.isEmpty) return const [];

    final scored = <({String id, String name, String location, int? quantity, double score})>[];

    for (final item in db.items) {
      final s = _score(item, terms);
      if (s > 0) {
        scored.add((
          id: item.id,
          name: item.name,
          location: db.breadcrumb(item.locationId),
          quantity: item.quantity,
          score: s,
        ));
      }
    }

    scored.sort((a, b) => b.score.compareTo(a.score));
    return scored
        .take(10)
        .map((r) => (id: r.id, name: r.name, location: r.location, quantity: r.quantity))
        .toList();
  }

  static const _stopwords = {
    'where', 'are', 'is', 'my', 'the', 'a', 'an', 'do', 'i', 'have', 'find', 'get',
  };

  static List<String> _queryTerms(String query) {
    return _normalize(query)
        .split(' ')
        .where((w) => w.isNotEmpty && !_stopwords.contains(w))
        .toList();
  }

  static String _normalize(String term) {
    final t = term.toLowerCase().replaceAll(RegExp(r'[^a-z0-9 ]+'), ' ');
    return t.split(' ').where((w) => w.isNotEmpty).map((w) {
      if (w.length > 3 && w.endsWith('es')) {
        final stem = w.substring(0, w.length - 2);
        if (RegExp(r'(?:s|x|z|ch|sh)$').hasMatch(stem)) return stem; // boxes, watches
      }
      if (w.length > 3 && w.endsWith('s') && !w.endsWith('ss')) {
        return w.substring(0, w.length - 1); // nuts -> nut, ties -> tie
      }
      return w;
    }).join(' ');
  }

  static double _score(Item item, List<String> terms) {
    final nameTokens = _normalize(item.name).split(' ').toSet();
    final tagTokens = item.tags.expand((t) => _normalize(t).split(' ')).toSet();
    final ocrTokens = _normalize(item.ocrText ?? '').split(' ').toSet();

    var score = 0.0;
    for (final term in terms) {
      if (nameTokens.contains(term)) {
        score += 3.0;
      } else if (tagTokens.contains(term)) {
        score += 1.5;
      } else if (ocrTokens.contains(term)) {
        score += 1.0;
      }
    }
    return score / terms.length;
  }
}
