import 'package:flutter/material.dart';

import 'features/capture/capture_screen.dart';
import 'features/locations/locations_screen.dart';
import 'features/search/search_screen.dart';

// NOTE: Amplify initialization is intentionally deferred until the backend is
// deployed (`ampx sandbox` generates `amplify_outputs.dart`). Once present, wrap
// runApp with Amplify.configure(...) using the generated outputs. See README.

void main() {
  runApp(const WheresMyStuffApp());
}

class WheresMyStuffApp extends StatelessWidget {
  const WheresMyStuffApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: "Where's My Stuff",
      theme: ThemeData(colorSchemeSeed: Colors.teal, useMaterial3: true),
      home: const HomeShell(),
    );
  }
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  static const _tabs = [
    SearchScreen(),
    LocationsScreen(),
    CaptureScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _tabs[_index],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.search), label: 'Find'),
          NavigationDestination(icon: Icon(Icons.shelves), label: 'Browse'),
          NavigationDestination(icon: Icon(Icons.add_a_photo), label: 'Add'),
        ],
      ),
    );
  }
}
