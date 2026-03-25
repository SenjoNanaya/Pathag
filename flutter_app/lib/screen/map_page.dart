import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:image_picker/image_picker.dart';
import 'package:latlong2/latlong.dart';

class MapPage extends StatefulWidget {
  const MapPage({super.key});

  @override
  State<MapPage> createState() => _MapPage();
}

class _MapPage extends State<MapPage> {
  final TextEditingController _pointAController = TextEditingController();
  final TextEditingController _pointBController = TextEditingController();

  final TextEditingController _obstacleLatController = TextEditingController();
  final TextEditingController _obstacleLonController = TextEditingController();
  final TextEditingController _reporterIdController =
      TextEditingController(text: '1');
  final TextEditingController _verifierId1Controller =
      TextEditingController(text: '1');
  final TextEditingController _verifierId2Controller =
      TextEditingController(text: '2');

  final ImagePicker _picker = ImagePicker();

  LatLng? pointA;
  LatLng? pointB;
  List<Polyline> routeLines = [];

  // Change this for your environment.
  static const String httpBaseUrl = 'http://localhost:8000';

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

  Future<void> _searchLocations() async {
    setState(() {
      pointA = uplbLandmarks[_pointAController.text.toLowerCase().trim()];
      pointB = uplbLandmarks[_pointBController.text.toLowerCase().trim()];
    });

    if (pointA == null || pointB == null) {
      String missing = pointA == null ? "Point A" : "Point B";
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
              "Could not find location for $missing. Try 'PhySci' or 'Main Lib'."),
        ),
      );
      setState(() => routeLines = []);
      return;
    }

    setState(() {
      _obstacleLatController.text = _obstacleLatController.text.isEmpty
          ? pointA!.latitude.toString()
          : _obstacleLatController.text;
      _obstacleLonController.text = _obstacleLonController.text.isEmpty
          ? pointA!.longitude.toString()
          : _obstacleLonController.text;
    });

    try {
      final route = await _calculateRoute(pointA!, pointB!);
      setState(() {
        routeLines = [
          Polyline(
            points: route,
            color: Colors.blue[800]!,
            strokeWidth: 4.0,
          ),
        ];
      });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Route calculation failed: $e")),
      );
    }
  }

  Future<List<LatLng>> _calculateRoute(LatLng origin, LatLng destination) async {
    final uri = Uri.parse('$httpBaseUrl/api/v1/routes/calculate');
    final payload = {
      "origin": {"latitude": origin.latitude, "longitude": origin.longitude},
      "destination": {
        "latitude": destination.latitude,
        "longitude": destination.longitude
      },
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
      final lon = (arr[0] as num).toDouble();
      final lat = (arr[1] as num).toDouble();
      return LatLng(lat, lon);
    }).toList();
  }

  Future<void> _captureAndReportObstacle() async {
    if (pointA == null || pointB == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Choose Point A and Point B first.")),
      );
      return;
    }

    final obstacleLat = double.tryParse(_obstacleLatController.text.trim());
    final obstacleLon = double.tryParse(_obstacleLonController.text.trim());
    final reporterId = int.tryParse(_reporterIdController.text.trim());
    final verifierId1 = int.tryParse(_verifierId1Controller.text.trim());
    final verifierId2Raw = int.tryParse(_verifierId2Controller.text.trim());

    if (obstacleLat == null ||
        obstacleLon == null ||
        reporterId == null ||
        verifierId1 == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text("Fill obstacle lat/lon + reporter/verifier IDs.")),
      );
      return;
    }

    final picked = await _picker.pickImage(source: ImageSource.camera);
    if (picked == null) return;

    final bytes = await picked.readAsBytes();
    final base64Image = base64Encode(bytes);

    final wsUrl =
        httpBaseUrl.replaceFirst('http', 'ws') + '/api/v1/realtime/obstacles/stream';
    final wsUri = Uri.parse(wsUrl);

    final completer = Completer<Map<String, dynamic>>();
    WebSocket? ws;

    try {
      ws = await WebSocket.connect(wsUri.toString());
      ws.listen((message) async {
        try {
          final data = jsonDecode(message) as Map<String, dynamic>;
          if (!completer.isCompleted) {
            completer.complete(data);
          }
        } catch (e) {
          if (!completer.isCompleted) {
            completer.completeError(e);
          }
        } finally {
          await ws?.close();
        }
      });

      ws.add(jsonEncode({
        "image_base64": base64Image,
        "latitude": obstacleLat,
        "longitude": obstacleLon,
      }));

      final classification = await completer.future.timeout(
        const Duration(seconds: 60),
      );

      final suggestedReportKind =
          (classification['suggested_report_kind'] as String?) ?? 'obstacle';
      if (suggestedReportKind == 'none') {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Verifiers suggest no report; skipping.")),
        );
        return;
      }

      // If surface_problem was chosen, backend suggests broken_pavement.
      final suggestedObstacleType =
          (classification['suggested_obstacle_type'] as String?) ??
              (classification['obstacle_type'] as String);

      final suggestedSeverity =
          (classification['suggested_severity'] as num).toInt();

      final reportId = await _createObstacleReport(
        reporterId: reporterId,
        latitude: obstacleLat,
        longitude: obstacleLon,
        obstacleType: suggestedObstacleType,
        severity: suggestedSeverity,
        isTemporary: true,
        description: suggestedReportKind == 'surface_problem'
            ? 'realtime capture (surface problem)'
            : 'realtime capture (obstacle)',
      );

      await _verifyObstacleReport(
        reportId: reportId,
        verifierId: verifierId1,
      );
      if (verifierId2Raw != null) {
        await _verifyObstacleReport(
          reportId: reportId,
          verifierId: verifierId2Raw,
        );
      }

      final route = await _calculateRoute(pointA!, pointB!);
      setState(() {
        routeLines = [
          Polyline(
            points: route,
            color: Colors.blue[800]!,
            strokeWidth: 4.0,
          ),
        ];
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
              "Reported $suggestedReportKind; verified; route updated."),
        ),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Realtime flow failed: $e")),
      );
      try {
        await ws?.close();
      } catch (_) {}
    }
  }

  Future<int> _createObstacleReport({
    required int reporterId,
    required double latitude,
    required double longitude,
    required String obstacleType,
    required int severity,
    required bool isTemporary,
    required String description,
  }) async {
    final uri = Uri.parse('$httpBaseUrl/api/v1/obstacles/reports');
    final payload = {
      "reporter_id": reporterId,
      "latitude": latitude,
      "longitude": longitude,
      "obstacle_type": obstacleType,
      "description": description,
      "severity": severity,
      "is_temporary": isTemporary,
    };

    final client = HttpClient();
    final req = await client.postUrl(uri);
    req.headers.contentType = ContentType.json;
    req.write(jsonEncode(payload));

    final resp = await req.close();
    final body = await resp.transform(utf8.decoder).join();
    client.close(force: true);

    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw Exception('Create report HTTP ${resp.statusCode}: $body');
    }

    final data = jsonDecode(body) as Map<String, dynamic>;
    return (data['id'] as num).toInt();
  }

  Future<void> _verifyObstacleReport({
    required int reportId,
    required int verifierId,
  }) async {
    final uri =
        Uri.parse('$httpBaseUrl/api/v1/obstacles/reports/$reportId/verify');
    final payload = {
      "verifier_id": verifierId,
      "notes": "realtime verify",
    };

    final client = HttpClient();
    final req = await client.postUrl(uri);
    req.headers.contentType = ContentType.json;
    req.write(jsonEncode(payload));

    final resp = await req.close();
    final body = await resp.transform(utf8.decoder).join();
    client.close(force: true);

    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw Exception('Verify HTTP ${resp.statusCode}: $body');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Pathag Search')),
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
                  if (pointA != null)
                    Marker(
                      point: pointA!,
                      child: const Icon(Icons.location_on,
                          color: Colors.green, size: 40),
                    ),
                  if (pointB != null)
                    Marker(
                      point: pointB!,
                      child:
                          const Icon(Icons.location_on, color: Colors.red, size: 40),
                    ),
                ],
              ),
            ],
          ),
          Positioned(
            top: 20,
            left: 15,
            right: 15,
            child: Card(
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(15)),
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
                    const SizedBox(height: 12),
                    TextField(
                      controller: _obstacleLatController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        hintText: "Report latitude",
                      ),
                    ),
                    TextField(
                      controller: _obstacleLonController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        hintText: "Report longitude",
                      ),
                    ),
                    TextField(
                      controller: _reporterIdController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        hintText: "reporter_id",
                      ),
                    ),
                    TextField(
                      controller: _verifierId1Controller,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        hintText: "verifier_id_1",
                      ),
                    ),
                    TextField(
                      controller: _verifierId2Controller,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        hintText: "verifier_id_2 (optional)",
                      ),
                    ),
                    const SizedBox(height: 10),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.green[800],
                          foregroundColor: Colors.white,
                        ),
                        onPressed: _captureAndReportObstacle,
                        child: const Text("Capture & Auto-Report"),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}