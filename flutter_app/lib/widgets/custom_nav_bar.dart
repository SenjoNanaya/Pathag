import 'package:flutter/material.dart';
import 'nav_handler.dart';
import '../screen/map_page.dart';
import '../screen/profile.dart';
import '../screen/report.dart';

class CustomNavBar extends StatelessWidget {
  final int selectedIndex;

  const CustomNavBar({super.key, required this.selectedIndex});

  @override
  Widget build(BuildContext context) {
    return BottomAppBar(
      color: Colors.white,
      elevation: 25,
      padding: EdgeInsets.zero,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _buildNavButton(context, Icons.person, "PROFILE", 0, const ProfilePage(currentIndex: 0)),
          _buildNavButton(context, Icons.map, "MAP", 1, const MapPage(currentIndex: 1)),
          _buildNavButton(context, Icons.report_gmailerrorred, "REPORT", 2, const ReportPage(currentIndex: 2)),
        ],
      ),
    );
  }

  Widget _buildNavButton(BuildContext context, IconData icon, String label, int index, Widget targetPage) {
    bool active = selectedIndex == index;
    final Color itemColor = active ? Colors.blue[800]! : Colors.grey[600]!;

    return Expanded(
      child: InkWell(
        onTap: () {
          if (active) return; // Don't reload if already on the page
          NavHandler.goToPage(context, targetPage);
        },
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, color: itemColor, size: 28),
              Text(
                label,
                style: TextStyle(
                  fontSize: 10,
                  color: itemColor,
                  fontWeight: active ? FontWeight.bold : FontWeight.normal,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}