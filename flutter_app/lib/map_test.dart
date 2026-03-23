import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart'; 

class MapTest extends StatefulWidget {
  const MapTest({super.key});

  @override
  State<MapTest> createState() => _MapTest();
}

class _MapTest extends State<MapTest> {
  @override
  Widget build (BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Pathag Map'
        ),
        leading: IconButton(
          onPressed: () => Navigator.pop(context), 
          icon: const Icon(Icons.arrow_back_ios_new_outlined)
        ),
      ),
      body: _buildBody()
    );
  }

  Widget _buildBody(){
    return FlutterMap(
      options: MapOptions(
        initialCenter: LatLng(14.1675, 121.2431),   // Los Baños, Laguna
        initialZoom: 18                             // How close is the map initially? 
      ),
      children: [
        TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'com.pathag.app',
        )
      ],
    );
  }
}