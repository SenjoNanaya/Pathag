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

  final TextEditingController _pointAController = TextEditingController();
  final TextEditingController _pointBController = TextEditingController();

  LatLng? pointA;
  LatLng? pointB;
  List<Polyline> routeLines = [];

  static const String httpBaseUrl = 'http://localhost:8000';

  final Map<String, LatLng> uplbLandmarks = {
    'uplb gate': const LatLng(14.1675, 121.2431),
    'physci': const LatLng(14.1648, 121.2420),
    'main lib': const LatLng(14.1653, 121.2400),
    'student union': const LatLng(14.1645, 121.2440),
    'raymundo gate': const LatLng(14.1610, 121.2450),
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
              strokeWidth: 4.0,
            ),
          ];
          _isSearching = false; 
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Route Calculation Failed: $e")),
        );
      }
    }
  }

  Future<List<LatLng>> _calculateRoute(LatLng origin, LatLng destination) async {
    final uri = Uri.parse('$httpBaseUrl/api/v1/routes/calculate');
    final payload = {
      "origin": {"latitude": origin.latitude, "longitude": origin.longitude},
      "destination": {"latitude": destination.latitude, "longitude": destination.longitude},
    };

    final client = HttpClient();
    final req = await client.postUrl(uri);
    req.headers.contentType = ContentType.json;
    req.write(jsonEncode(payload));

    final resp = await req.close();
    final body = await resp.transform(utf8.decoder).join();
    client.close(force: true);

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
          _createSearchUI(),
        ],
      ),
      bottomNavigationBar: CustomNavBar(selectedIndex: widget.currentIndex),
    );
  }
}