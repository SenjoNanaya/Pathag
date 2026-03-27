import 'package:flutter/material.dart';
import 'nav_handler.dart';
import '../screen/map_page.dart';
import '../screen/profile.dart';
import '../screen/report.dart';

class CustomNavBar extends StatelessWidget {
  final int selectedIndex;
  final ValueChanged<int>? onTapIndex;

  const CustomNavBar({
    super.key,
    required this.selectedIndex,
    this.onTapIndex,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        // Match the rounded vibe of your Profile header
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(20),
          topRight: Radius.circular(20),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.08),
            blurRadius: 15,
            offset: const Offset(0, -5), // Shadow cast upwards
          ),
        ],
        border: Border(
          top: BorderSide(color: Colors.grey[100]!, width: 1),
        ),
      ),
      child: ClipRRect( // Ensures the inkwell splash stays within the rounded corners
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(20),
          topRight: Radius.circular(20),
        ),
        child: BottomAppBar(
          color: Colors.white,
          elevation: 0,
          padding: EdgeInsets.zero,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildNavButton(context, Icons.person_rounded, "PROFILE", 0, const ProfilePage(currentIndex: 0)),
              _buildNavButton(context, Icons.map_rounded, "MAP", 1, const MapPage(currentIndex: 1)),
              _buildNavButton(context, Icons.report_gmailerrorred_rounded, "REPORT", 2, const ReportPage(currentIndex: 2)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildNavButton(BuildContext context, IconData icon, String label, int index, Widget targetPage) {
    bool active = selectedIndex == index;
    final Color itemColor = active ? Colors.blue[800]! : Colors.grey[600]!;

    return Expanded(
      child: InkWell(
        onTap: () {
          if (active) return;
          if (onTapIndex != null) {
            onTapIndex!(index);
            return;
          }
          NavHandler.goToPage(context, targetPage);
        },
        child: Column(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center, // Center items vertically
          children: [
            Icon(icon, color: itemColor, size: 26),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 10,
                color: itemColor,
                fontWeight: active ? FontWeight.w900 : FontWeight.w500,
                letterSpacing: 0.5,
              ),
            ),
          ],
        ),
      ),
    );
  }
}