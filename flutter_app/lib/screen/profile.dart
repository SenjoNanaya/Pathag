import 'package:flutter/material.dart';
import '../widgets/custom_nav_bar.dart';

class ProfilePage extends StatefulWidget {
  final int currentIndex;
  const ProfilePage({super.key, required this.currentIndex});

  @override
  State<ProfilePage> createState() => _ProfilePage();
}

class _ProfilePage extends State<ProfilePage> {
  @override
  void initState() {
    super.initState();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: const Center(
        child: Text("ProfilePage, ano tara?"),
      ),
      bottomNavigationBar: const CustomNavBar(selectedIndex: 0)
    );
  }
}