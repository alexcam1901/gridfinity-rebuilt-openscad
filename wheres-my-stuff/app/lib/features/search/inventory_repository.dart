/// Search results returned by the `query` Lambda.
class MatchResult {
  final String id;
  final String name;
  final String location; // breadcrumb, e.g. "Garage > Wall shelf B > Bin 3"
  final int? quantity;

  const MatchResult({
    required this.id,
    required this.name,
    required this.location,
    this.quantity,
  });

  factory MatchResult.fromJson(Map<String, dynamic> json) => MatchResult(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? '',
        location: json['location'] as String? ?? '',
        quantity: json['quantity'] as int?,
      );
}

/// Talks to the backend `query` Lambda (via AppSync) and falls back to the local
/// SQLite cache when offline. Wired to Amplify API once the backend is deployed.
class InventoryRepository {
  Future<List<MatchResult>> search(String query) async {
    // TODO: call Amplify.API GraphQL `searchItems(query:)` -> rank_matches.
    // Placeholder so the UI runs before the backend is deployed.
    if (query.trim().isEmpty) return const [];
    return const [
      MatchResult(
        id: 'demo',
        name: 'wire nuts',
        location: 'Garage > Wall shelf B > Bin 3',
        quantity: 100,
      ),
    ];
  }
}
