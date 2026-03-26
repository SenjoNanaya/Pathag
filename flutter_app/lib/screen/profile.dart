import 'package:flutter/material.dart';
import '../widgets/custom_nav_bar.dart';

class ProfilePage extends StatefulWidget {
  final int currentIndex;
  const ProfilePage({super.key, this.currentIndex = 0});

  @override
  State<ProfilePage> createState() => _ProfilePage();
}

class _ProfilePage extends State<ProfilePage> {

  // PURPOSE: Dummy Account - Mocking a User Data
  Map<String, dynamic> account = {
    "name": "Bab",
    "yearJoined": 2026,
    "category": "Crutches",
    "filter": ["Uneven Path", "Steep Inclines"]
  };

  // === | UI HELPERS | ===

  Widget _sectionHeader(String text) {
    return Text(
      text,
      style: TextStyle(
        fontWeight: FontWeight.bold,
        fontSize: 16,
        color: Colors.blue[800],
      ),
    );
  }

  Widget _buildBody(){
    return Column(
      children: [
        _buildProfileHeader(),
        Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // == | ACCESSIBILITY PROFILE SECTION | ==
              _sectionHeader("MOBILITY CATEGORY"),
              const SizedBox(height: 10),
              _buildInfoCard(
                icon: Icons.accessible_forward_rounded, 
                title: account["category"], 
                subtitle: "your primary mobility assistance type"
              ),
              const SizedBox(height:30),

              // == | THINGS TO AVOID (FILTERS) | ==
              _sectionHeader("ROUTE PREFERENCES"),
              const SizedBox(height: 5),
              Text (
                "Pathag will avoid these micro-impediments during navigation.",
                style: TextStyle(
                  color: Colors.grey,
                  fontSize: 12
                ),
              ),
              const SizedBox(height: 15),

              Wrap(
                spacing: 8.0,
                runSpacing: 8.0,
                children: (account["filter"] as List<String>).map((filter) {
                  return Chip(
                    label: Text(filter),
                    backgroundColor: Colors.blue[50],
                    labelStyle: TextStyle(
                      color: Colors.blue[800],
                      fontWeight: FontWeight.bold,
                      fontSize: 13,
                    ),
                    side: BorderSide(color: Colors.blue[100]!),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                    avatar: Icon(Icons.block_flipped, size: 16, color: Colors.blue[800]),
                  );
                }).toList(),
              ),
              const SizedBox(height: 30),

              // == | ACCOUNT ACTIONS | ==
              _buildActionTile(Icons.edit_note_rounded, "Edit Accessibility Profile"),
              _buildActionTile(Icons.history_rounded, "Your Reported Obstacles"),
              _buildActionTile(Icons.logout_rounded, "Logout", isDestructive: true),
            ],
          )
        )
      ],
    );
  }

  Widget _buildProfileHeader() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(30, 60, 30, 40),
      decoration: BoxDecoration(
        color: Colors.blue[800],
        borderRadius: const BorderRadius.only(
          bottomLeft: Radius.circular(30),
          bottomRight: Radius.circular(30),
        ),
      ),
      child: Column(
        children: [

          // == | PROFILE PICTURE | ===
          CircleAvatar(
            radius: 50,
            backgroundColor: Colors.white,
            child: Icon(Icons.person_rounded, size: 60, color: Colors.blue[800]),
          ),
          const SizedBox(height: 15),

          // == | USERNAME | ==
          Text(
            account["name"],
            style: const TextStyle(
              color: Colors.white,
              fontSize: 24,
              fontWeight: FontWeight.w900,
              letterSpacing: 1.2,
            ),
          ),
          
          // == | DATE JOINED | ===
          Text(
            'UPLB Student • Joined ${account["yearJoined"]}',
            style: TextStyle(color: Colors.blue[100], fontSize: 14),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: _buildBody()
      ),
      bottomNavigationBar: const CustomNavBar(selectedIndex: 0)
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