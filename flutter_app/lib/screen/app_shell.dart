import 'package:flutter/material.dart';
import '../widgets/custom_nav_bar.dart';
import 'map_page.dart';
import 'profile.dart';
import 'report.dart';

class AppShell extends StatefulWidget {
  final int initialIndex;
  const AppShell({super.key, this.initialIndex = 1});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  late int _currentIndex;

  @override
  void initState() {
    super.initState();
    _currentIndex = widget.initialIndex.clamp(0, 2);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: const [
          ProfilePage(currentIndex: 0, showNavBar: false),
          MapPage(currentIndex: 1, showNavBar: false),
          ReportPage(currentIndex: 2, showNavBar: false),
        ],
      ),
      bottomNavigationBar: CustomNavBar(
        selectedIndex: _currentIndex,
        onTapIndex: (index) {
          setState(() => _currentIndex = index);
        },
      ),
    );
  }
}

