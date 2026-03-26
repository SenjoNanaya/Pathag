import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import '../widgets/custom_nav_bar.dart';

class MapPage extends StatefulWidget {
  final int currentIndex;
  const MapPage({super.key, this.currentIndex = 1});

  @override
  State<MapPage> createState() => _MapPage();
}

class _MapPage extends State<MapPage> {
  bool _isSearching = false;
  bool _isNavigating = false;

  final TextEditingController _pointAController = TextEditingController();
  final TextEditingController _pointBController = TextEditingController();

  LatLng? pointA;
  LatLng? pointB;
  List<Polyline> routeLines = [];

  static String get _httpBaseUrl =>
      Platform.isAndroid ? 'http://10.0.2.2:8000' : 'http://localhost:8000';

  final Map<String, LatLng> uplbLandmarks = {
    'uplb gate': const LatLng(14.1675, 121.2431),
    'physci': const LatLng(14.1648, 121.2420),
    'main lib': const LatLng(14.1653, 121.2400),
    'student union': const LatLng(14.1645, 121.2440),
    'raymundo gate': const LatLng(14.168009836121477, 121.24160711067458),
  };

  // PURPOSE: Path Summary Dummy Data
  Map<String, dynamic> pathSummary = {
    "rating": 85,
    "obstaclesEncountered": {
      "noSidewalk": 0,
      "unevenPath": 2,
      "obstruction": 3
    }
  };

  // === | NAVIGATION LOGIC | ===

  Future<void> _searchLocations() async {
    final start = uplbLandmarks[_pointAController.text.toLowerCase().trim()];
    final end = uplbLandmarks[_pointBController.text.toLowerCase().trim()];

    if (start == null || end == null) {
      String missing = start == null ? "Point A" : "Point B";
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Could not find location for $missing.")),
      );
      setState(() => routeLines = []);
      return;
    }

    setState(() {
      pointA = start;
      pointB = end;
    });

    try {
      final route = await _calculateRoute(start, end);
      
      if (mounted) {
        setState(() {
          routeLines = [
            Polyline(
              points: route,
              color: Colors.blue[800]!,
              strokeWidth: 5.0,
            ),
          ];
          _isSearching = false; 
        });

        _showRouteSummary();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Route calculation failed: $e")),
        );
      }
    }
  }

  // == | ROUTE DECISION | ==
  void _acceptRoute() {
    setState(() {
      _isNavigating = true; 
    });
    Navigator.pop(context);
  }

  void _rejectRoute() {
    setState(() {
      routeLines = [];
      pointA = null;
      pointB = null;
      _isNavigating = false;
    });
    Navigator.pop(context);
  }

  // == | ROUTE CALCULATION | ==

  Future<List<LatLng>> _calculateRoute(LatLng origin, LatLng destination) async {
    final uri = Uri.parse('$_httpBaseUrl/api/v1/routes/calculate');
    final payload = {
      "origin": {"latitude": origin.latitude, "longitude": origin.longitude},
      "destination": {"latitude": destination.latitude, "longitude": destination.longitude},
    };

    final client = HttpClient()..connectionTimeout = const Duration(seconds: 10);
    try {
      final req = await client.postUrl(uri);
      req.headers.contentType = ContentType.json;
      req.write(jsonEncode(payload));

      final resp = await req.close().timeout(const Duration(seconds: 20));
      final body = await resp.transform(utf8.decoder).join();

      if (resp.statusCode < 200 || resp.statusCode >= 300) {
        throw Exception('HTTP ${resp.statusCode}: $body');
      }

      final data = jsonDecode(body) as Map<String, dynamic>;
      final coords = (data['coordinates'] as List).cast<dynamic>();

      return coords.map((p) {
        final arr = (p as List).cast<dynamic>();
        // Backend returns [Lon, Lat], LatLng needs [Lat, Lon]
        return LatLng((arr[1] as num).toDouble(), (arr[0] as num).toDouble());
      }).toList();
    } on SocketException {
      throw Exception(
        'Cannot connect to backend at $_httpBaseUrl. Ensure FastAPI is running and reachable from this device.',
      );
    } on TimeoutException {
      throw Exception('Backend request timed out. Check server/network and try again.');
    } finally {
      client.close(force: true);
    }
  }

  // === | UI COMPONENTS | ===

  Widget _createSearchUI() {
    return Positioned(
      top: 50, left: 15, right: 15,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 400),
        curve: Curves.easeInOut,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(_isSearching ? 15 : 30),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.1),
              blurRadius: 10,
              offset: const Offset(0, 5),
            ),
          ],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(_isSearching ? 15 : 30),
          child: AnimatedCrossFade(
            firstChild: _buildCompactSearch(),
            secondChild: _buildExpandedSearch(),
            crossFadeState: _isSearching ? CrossFadeState.showSecond : CrossFadeState.showFirst,
            duration: const Duration(milliseconds: 400),
          ),
        ),
      ),
    );
  }

  Widget _buildCompactSearch() {
    return InkWell(
      onTap: () => setState(() => _isSearching = true),
      child: const Padding(
        padding: EdgeInsets.symmetric(horizontal: 20, vertical: 15),
        child: Row(
          children: [
            Icon(Icons.search, color: Colors.grey),
            SizedBox(width: 10),
            Text("Search campus landmarks...", style: TextStyle(color: Colors.grey)),
          ],
        ),
      ),
    );
  }

  Widget _buildExpandedSearch() {
    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text("FIND ROUTE", 
                style: TextStyle(fontWeight: FontWeight.bold, color: Colors.blue[800], fontSize: 16)
              ),
              IconButton(
                icon: const Icon(Icons.close, size: 20),
                onPressed: () => setState(() => _isSearching = false),
              )
            ],
          ),
          TextField(
            controller: _pointAController,
            decoration: const InputDecoration(
              hintText: "Start Point (e.g., PhySci)",
              hintStyle: TextStyle(color: Colors.grey, fontSize: 14),
              prefixIcon: Icon(Icons.circle_outlined, color: Colors.green, size: 20),
              border: InputBorder.none,
            ),
          ),
          const Divider(height: 1),
          TextField(
            controller: _pointBController,
            decoration: const InputDecoration(
              hintText: "Destination (e.g., Main Lib)",
              hintStyle: TextStyle(color: Colors.grey, fontSize: 14),
              prefixIcon: Icon(Icons.location_on, color: Colors.red, size: 20),
              border: InputBorder.none,
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            height: 45,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.blue[800],
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              onPressed: _searchLocations,
              child: const Text("FIND PATH"),
            ),
          ),
        ],
      ),
    );
  }

  // === | PATH SUMMARY | ===
  void _showRouteSummary() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true, 
      backgroundColor: Colors.transparent,
      builder: (context) => _buildPathSummary(),
    );
  }

  Widget _buildPathSummary() {
    final obstacles = pathSummary["obstaclesEncountered"];
    
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(25)),
      ),
      padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Visual Grabber
          Container(width: 40, height: 4, decoration: BoxDecoration(color: Colors.grey[300], borderRadius: BorderRadius.circular(10))),
          const SizedBox(height: 20),

          // Header Row
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text("Optimized Route", style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
                  Text("Estimated 5-8 mins walk", style: TextStyle(color: Colors.grey[600], fontSize: 13)),
                ],
              ),
              _buildRatingBadge(),
            ],
          ),
          const SizedBox(height: 20),

          // CHANGE: Added horizontal obstacle scroll for cleaner space usage
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _obstacleChip(Icons.report_problem_rounded, "${obstacles['unevenPath']} Uneven"),
                const SizedBox(width: 8),
                _obstacleChip(Icons.construction_rounded, "${obstacles['obstruction']} Blocked"),
                const SizedBox(width: 8),
                _obstacleChip(Icons.do_not_disturb_on_rounded, "No Path"),
              ],
            ),
          ),
          
          const Divider(height: 40),

          // ACTION BUTTONS (Refined Layout)
          Row(
            children: [
              Expanded(
                child: TextButton(
                  onPressed: _rejectRoute,
                  child: Text("REJECT", style: TextStyle(color: Colors.grey[600], fontWeight: FontWeight.bold)),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                flex: 2,
                child: ElevatedButton(
                  onPressed: _acceptRoute,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blue[800],
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    padding: const EdgeInsets.symmetric(vertical: 16),
                  ),
                  child: const Text("START NAVIGATION", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // === | HELPER WIDGETS | ===

  // CHANGE: Consistent Badge style for the Accessibility Score
  Widget _buildRatingBadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.blue[50], // Light blue background for contrast
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.blue[100]!),
      ),
      child: Column(
        children: [
          Text(
            "${pathSummary['rating']}%",
            style: TextStyle(
              color: Colors.blue[800],
              fontWeight: FontWeight.w900,
              fontSize: 18,
            ),
          ),
          Text(
            "Access Score",
            style: TextStyle(color: Colors.blue[800], fontSize: 10, fontWeight: FontWeight.bold),
          ),
        ],
      ),
    );
  }

  // CHANGE: Refined Obstacle Chip with consistent Grey[100] fill
  Widget _obstacleChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.grey[100],
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey[200]!),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 18, color: Colors.blue[800]),
          const SizedBox(width: 8),
          Text(
            label,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: Colors.black87,
            ),
          ),
        ],
      ),
    );
  }

  // NEW: Active Navigation HUD (Floating Bar)
  Widget _buildNavigationHud() {
    return Positioned(
      bottom: 30, // Floats above the bottom of the screen
      left: 20,
      right: 20,
      child: Container(
        height: 70,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        decoration: BoxDecoration(
          color: Colors.blue[800],
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.2),
              blurRadius: 15,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Row(
          children: [
            const Icon(Icons.navigation_rounded, color: Colors.white, size: 28),
            const SizedBox(width: 15),
            const Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    "NAVIGATING",
                    style: TextStyle(color: Colors.white70, fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 1.2),
                  ),
                  Text(
                    "Follow the blue path",
                    style: TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ),
            // CHANGE: Integrated Quick-Report shortcut for accessibility
            IconButton(
              icon: const Icon(Icons.add_a_photo_rounded, color: Colors.white),
              onPressed: () {
                // Future Logic: Jump straight to ReportPage with coordinates
              },
            ),
            const VerticalDivider(color: Colors.white24, indent: 15, endIndent: 15),
            IconButton(
              icon: const Icon(Icons.close_rounded, color: Colors.white),
              onPressed: () => setState(() => _isNavigating = false),
            ),
          ],
        ),
      ),
    );
  }

  // === | FRONT-END | ===

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      resizeToAvoidBottomInset: false,
      body: Stack(
        children: [
          FlutterMap(
            options: const MapOptions(
              initialCenter: LatLng(14.1675, 121.2431),
              initialZoom: 16,
            ),
            children: [
              TileLayer(
                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.pathag.app',
              ),
              PolylineLayer(polylines: routeLines),
              MarkerLayer(
                markers: [
                  if (pointA != null) Marker(
                    point: pointA!, 
                    child: const Icon(Icons.location_on, color: Colors.green, size: 40)
                  ),
                  if (pointB != null) Marker(
                    point: pointB!, 
                    child: const Icon(Icons.location_on, color: Colors.red, size: 40)
                  ),
                ],
              ),
            ],
          ),
          if(!_isNavigating) _createSearchUI(),
          if(_isNavigating) _buildNavigationHud()
        ],
      ),
      bottomNavigationBar: _isNavigating ? null : CustomNavBar(selectedIndex: widget.currentIndex),
    );
  }
}