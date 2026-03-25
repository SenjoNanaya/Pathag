import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

class MapTest extends StatefulWidget {
  const MapTest({super.key});

  @override
  State<MapTest> createState() => _MapTest();
}

class _MapTest extends State<MapTest> {
  final LatLng uplbGate = const LatLng(14.1675, 121.2431);
  final LatLng physciBldg = const LatLng(14.164813642210433, 121.24206606451793);

  List<Marker> userTags = []; // Storage for markers
  final Distance distanceCalc = const Distance(); // Distance Calculator

  // === | PURPOSE: Add Tag on Long Press | ===
  void _addTag(TapPosition tapPosition, LatLng point) {
    // Calculate distance from Physci to the new tag
    final double meters = distanceCalc.as(LengthUnit.Meter, physciBldg, point);

    setState(() {
      userTags.add(
        Marker(
          point: point,
          width: 80,
          height: 80,
          child: GestureDetector(
            onTap: () {
              // Show distance when the marker itself is tapped
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('Distance to Physci: ${meters.toStringAsFixed(2)}m')),
              );
            },
            child: const Icon(
              Icons.location_on,
              color: Colors.red,
              size: 40,
            ),
          ),
        ),
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Pathag Map'),
        leading: IconButton(
          onPressed: () => Navigator.pop(context),
          icon: const Icon(Icons.arrow_back_ios_new_outlined),
        ),
      ),
      body: _buildBody(),
      // Floating button to clear tags if it gets crowded
      floatingActionButton: FloatingActionButton(
        onPressed: () => setState(() => userTags.clear()),
        child: const Icon(Icons.layers_clear),
      ),
    );
  }

  Widget _buildBody() {
    return FlutterMap(
      options: MapOptions(
        initialCenter: uplbGate,
        initialZoom: 17,
        onLongPress: _addTag, // Trigger tag creation here
      ),
      children: [
        TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'com.pathag.app',
        ),
        // === | MARKER LAYER | ===
        MarkerLayer(
          markers: [
            // Static marker for Physci Bldg
            Marker(
              point: physciBldg,
              width: 80,
              height: 80,
              child: const Icon(Icons.school, color: Colors.blue, size: 40),
            ),
            // Dynamic markers from userTags list
            ...userTags,
          ],
        ),
      ],
    );
  }
}