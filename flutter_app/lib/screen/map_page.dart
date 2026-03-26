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
      //appBar: AppBar(title: const Text('Pathag Search')),
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

  Widget _createSearchUI() {
      return Positioned(
            top: 50,
            left: 15,
            right: 15,
            child: Card(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
              elevation: 8,
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: _pointAController,
                      decoration: const InputDecoration(
                        hintText: "Enter Point A (e.g., PhySci)",
                        prefixIcon: Icon(Icons.search, color: Colors.green),
                        border: InputBorder.none,
                      ),
                    ),
                    const Divider(),
                    TextField(
                      controller: _pointBController,
                      decoration: const InputDecoration(
                        hintText: "Enter Point B (e.g., Main Lib)",
                        prefixIcon: Icon(Icons.search, color: Colors.red),
                        border: InputBorder.none,
                      ),
                    ),
                    const SizedBox(height: 10),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.blue[800],
                          foregroundColor: Colors.white,
                        ),
                        onPressed: _searchLocations,
                        child: const Text("Find Path"),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
    }
}