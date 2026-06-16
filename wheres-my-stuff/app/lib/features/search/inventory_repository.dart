import '../../data/item_repository.dart';

/// Search result returned to the Find screen.
class MatchResult {
  final String id;
  final String name;
  final String location;
  final int? quantity;

  const MatchResult({
    required this.id,
    required this.name,
    required this.location,
    this.quantity,
  });
}

/// Searches the inventory using synonym-aware ranked matching.
///
/// Currently delegates to [ItemRepository] which runs against the in-memory
/// mock DB. Once deployed, swap the body to call the AppSync custom query:
///
/// ```dart
/// final result = await Amplify.API.query(request: GraphQLRequest<String>(
///   document: searchItemsQuery,
///   variables: {'query': query},
/// )).response;
/// // parse result.data into List<MatchResult>
/// ```
class InventoryRepository {
  final _itemRepo = ItemRepository();

  Future<List<MatchResult>> search(String query) async {
    final results = await _itemRepo.search(query);
    return results
        .map((r) => MatchResult(
              id: r.id,
              name: r.name,
              location: r.location,
              quantity: r.quantity,
            ))
        .toList();
  }
}
