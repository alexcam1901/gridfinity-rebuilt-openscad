import 'package:flutter/material.dart';

import '../../data/item_repository.dart';
import '../items/item_detail_screen.dart';
import 'inventory_repository.dart';

/// "Where is X" screen: type or speak a query, get ranked matches with a
/// location breadcrumb. Voice uses on-device speech_to_text for low latency;
/// the actual search runs synonym-aware matching (mirrors query Lambda logic).
class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final _controller = TextEditingController();
  final _repo = InventoryRepository();
  final _itemRepo = ItemRepository();
  List<MatchResult> _results = const [];
  bool _loading = false;

  Future<void> _run() async {
    setState(() => _loading = true);
    final results = await _repo.search(_controller.text);
    if (mounted) {
      setState(() {
        _results = results;
        _loading = false;
      });
    }
  }

  Future<void> _openItem(MatchResult match) async {
    final item = await _itemRepo.findById(match.id);
    if (item != null && mounted) {
      await Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => ItemDetailScreen(item: item)),
      );
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Find an item')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _controller,
              onSubmitted: (_) => _run(),
              decoration: InputDecoration(
                hintText: 'e.g. where are my wire nuts?',
                border: const OutlineInputBorder(),
                suffixIcon: IconButton(
                  icon: const Icon(Icons.mic),
                  // TODO: wire speech_to_text -> _controller.text -> _run().
                  onPressed: _run,
                ),
              ),
            ),
            const SizedBox(height: 12),
            if (_loading) const LinearProgressIndicator(),
            Expanded(
              child: _results.isEmpty && !_loading
                  ? const _EmptyState()
                  : ListView.builder(
                      itemCount: _results.length,
                      itemBuilder: (_, i) {
                        final m = _results[i];
                        return ListTile(
                          title: Text(m.name),
                          subtitle: Text(m.location),
                          trailing: m.quantity == null
                              ? null
                              : Text('×${m.quantity}'),
                          onTap: () => _openItem(m),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.search,
              size: 48, color: Theme.of(context).colorScheme.outline),
          const SizedBox(height: 12),
          Text('Try "wire nuts", "drill", or "batteries"',
              style: TextStyle(
                  color: Theme.of(context).colorScheme.outline)),
        ],
      ),
    );
  }
}
