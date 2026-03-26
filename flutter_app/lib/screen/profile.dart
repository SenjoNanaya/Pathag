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

  Widget _buildBody(){
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal:0),
      child: Column(
        children: [
          _buildProfileHeader()
        ],
      ),
    );
  }

  Widget _buildProfileHeader() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal:30),
      decoration: BoxDecoration(color: Colors.blue[800]),
      child: Text("ProfilePage, ano tara?")
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _buildBody(),
      bottomNavigationBar: const CustomNavBar(selectedIndex: 0)
    );
  }
}