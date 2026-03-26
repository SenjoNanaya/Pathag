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
  // PURPOSE: Track if Search UI is Expanded
  bool _isSearching = false;

  // PURPOSE: Track which Page is Active
  final TextEditingController _pointAController = TextEditingController();
  final TextEditingController _pointBController = TextEditingController();

  LatLng? pointA;
  LatLng? pointB;
  List<Polyline> routeLines = [];

  // === | CAMPUS LANDMARK DATABASE | ===
  // PURPOSE: Maps the User's Input String to Actual Coordinates
  // LIMIT: Only Recognizes Locations w/ Exact Keys
  final Map<String, LatLng> uplbLandmarks = {
    'uplb gate': const LatLng(14.1675, 121.2431),
    'physci': const LatLng(14.1648, 121.2420),
    'main lib': const LatLng(14.1653, 121.2400),
    'student union': const LatLng(14.1645, 121.2440),
    'raymundo gate': const LatLng(14.1610, 121.2450),
  };

  // PURPOSE: Finds LatLng Equivalent of the Input 
  void _searchLocations() {
    setState(() {
      // PURPOSE: Normalize input to lowercase to match the keys in our map
      pointA = uplbLandmarks[_pointAController.text.toLowerCase().trim()];
      pointB = uplbLandmarks[_pointBController.text.toLowerCase().trim()];

      // PURPOSE: Create a Polyline Only if Both Points Exist
      if (pointA != null && pointB != null) {
        routeLines = [
          Polyline(
            points: [pointA!, pointB!],
            color: Colors.blue[800]!,
            strokeWidth: 4.0,
          ),
        ];
        _isSearching = false;
      } else { routeLines = []; }
    });

    if (pointA == null || pointB == null) {
      String missing = pointA == null ? "Point A" : "Point B";
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Could not find location for $missing. Try 'PhySci' or 'Main Lib'.")),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      resizeToAvoidBottomInset: false,
      body: Stack(
        children: [

          // == | MAP | ==
          FlutterMap(
            options: const MapOptions(
              initialCenter: LatLng(14.1675, 121.2431),
              initialZoom: 16,
            ),
            children: [

              // = | MAP NAVIGATOR | =
              TileLayer(
                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.pathag.app',
              ),

              // = | POLYLINE (ROUTE) | =
              PolylineLayer(
                polylines: routeLines 
              ),

              // = | MARKER | =
              MarkerLayer(
                markers: [
                  if (pointA != null)
                    Marker(
                      point: pointA!,
                      child: const Icon(Icons.location_on, color: Colors.green, size: 40),
                    ),
                  if (pointB != null)
                    Marker(
                      point: pointB!,
                      child: const Icon(Icons.location_on, color: Colors.red, size: 40),
                    ),
                ],
              ),
            ],
          ),

          // == | SEARCH UI | ==
          _createSearchUI()
        ], 
      ),
      
      // === | NAVIGATION BUTTON BAR | ===
      bottomNavigationBar: const CustomNavBar(selectedIndex: 1)
    );
  }

  // === | SEARCH UI | ===
  // PURPOSE: Tracks what kind of Search UI is shown
  Widget _createSearchUI() {
    return Positioned(
      top: 50,
      left: 15,
      right: 15,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 400),
        curve: Curves.easeInOut,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(_isSearching ? 15 : 30),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.1),
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
            crossFadeState: _isSearching 
                ? CrossFadeState.showSecond 
                : CrossFadeState.showFirst,
            duration: const Duration(milliseconds: 400),
          ),
        ),
      ),
    );
  }

  // PURPOSE: Compact View - just a single bar
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

  // PURPOSE: Expanded View - Point A to Point B
  Widget _buildExpandedSearch() {
    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text("Find Route", 
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
              hintStyle: TextStyle(
                color: Colors.grey, 
                fontSize: 14,
              ),
              prefixIcon: Icon(Icons.circle_outlined, color: Colors.green, size: 20),
              border: InputBorder.none,
            ),
          ),
          const Divider(height: 1),
          TextField(
            controller: _pointBController,
            decoration: const InputDecoration(
              hintText: "Destination (e.g., Main Lib)",
              hintStyle: TextStyle(
                color: Colors.grey, 
                fontSize: 14,
              ),
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
}