import 'package:flutter/material.dart';
import '../widgets/custom_nav_bar.dart';

class ReportPage extends StatefulWidget {
  final int currentIndex;
  const ReportPage({super.key, required this.currentIndex});

  @override
  State<ReportPage> createState() => _ReportPage();
}

class _ReportPage extends State<ReportPage> {
  @override
  void initState() {
    super.initState();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: const Center(
        child: Text("ReportPage, ano tara?"),
      ),
      bottomNavigationBar: const CustomNavBar(selectedIndex: 2),
    );
  }
}