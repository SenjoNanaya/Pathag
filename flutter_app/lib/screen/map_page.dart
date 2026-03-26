import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'report.dart';
import '../widgets/custom_nav_bar.dart';

class _RouteResult {
  final List<LatLng> coordinates;
  final double accessibilityScore;
  final int estimatedDurationSeconds;
  final double distanceMeters;
  final List<String> warnings;
  final List<_NavigationStep> steps;

  _RouteResult({
    required this.coordinates,
    required this.accessibilityScore,
    required this.estimatedDurationSeconds,
    required this.distanceMeters,
    required this.warnings,
    required this.steps,
  });
}

class _NavigationStep {
  final double distance;
  final String instruction;
  final String pathCondition;
  final LatLng point;

  _NavigationStep({
    required this.distance,
    required this.instruction,
    required this.pathCondition,
    required this.point,
  });
}

class MapPage extends StatefulWidget {
  final int currentIndex;
  const MapPage({super.key, this.currentIndex = 1});

  @override
  State<MapPage> createState() => _MapPage();
}

class _MapPage extends State<MapPage> {
  bool _isSearching = false;
  bool _isNavigating = false;
  final MapController _mapController = MapController();

  final TextEditingController _pointAController = TextEditingController();
  final TextEditingController _pointBController = TextEditingController();

  LatLng? pointA;
  LatLng? pointB;
  List<Polyline> routeLines = [];
  List<_NavigationStep> _navigationSteps = [];
  int _activeStepIndex = 0;

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
    "rating": 0,
    "obstaclesEncountered": {
      "noSidewalk": 0,
      "unevenPath": 0,
      "obstruction": 0
    }
  };
  String _routeEtaLabel = "Estimated -- mins walk";

  static const double _defaultZoom = 16.0;
  static const double _routeFocusZoom = 18.8;
  static const double _navigationZoom = 19.8;

  // === | NAVIGATION LOGIC | ===

  Color _segmentColor(String pathCondition) {
    switch (pathCondition.toLowerCase()) {
      case 'uneven':
        return Colors.yellow;
      case 'cracked':
        return Colors.orange;
      case 'obstructed':
        return Colors.redAccent;
      case 'no_sidewalk':
        return Colors.deepPurple;
      default:
        return Colors.blue[800]!;
    }
  }

  List<Polyline> _buildRoutePolylines(_RouteResult routeResult) {
    final coords = routeResult.coordinates;
    if (coords.length < 2) {
      return const [];
    }

    // Route steps are per segment plus a final "arrived" step.
    // Color each segment using the matching step's path condition.
    final polylines = <Polyline>[];
    final segmentCount = coords.length - 1;
    for (var i = 0; i < segmentCount; i++) {
      final stepCondition = (i < routeResult.steps.length)
          ? routeResult.steps[i].pathCondition
          : 'smooth';
      polylines.add(
        Polyline(
          points: [coords[i], coords[i + 1]],
          color: _segmentColor(stepCondition),
          strokeWidth: 6.0,
        ),
      );
    }
    return polylines;
  }

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
      final routeResult = await _calculateRoute(start, end);
      
      if (mounted) {
        _updatePathSummary(routeResult);
        setState(() {
          _navigationSteps = routeResult.steps;
          _activeStepIndex = 0;
          routeLines = _buildRoutePolylines(routeResult);
          _isSearching = false; 
        });
        if (routeResult.coordinates.isNotEmpty) {
          _mapController.move(routeResult.coordinates.first, _routeFocusZoom);
        }

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
      _activeStepIndex = 0;
    });
    if (_navigationSteps.isNotEmpty) {
      _mapController.move(_navigationSteps.first.point, _navigationZoom);
    } else if (pointA != null) {
      _mapController.move(pointA!, _navigationZoom);
    }
    Navigator.pop(context);
  }

  void _rejectRoute() {
    setState(() {
      routeLines = [];
      _navigationSteps = [];
      _activeStepIndex = 0;
      pointA = null;
      pointB = null;
      _isNavigating = false;
    });
    Navigator.pop(context);
  }

  // == | ROUTE CALCULATION | ==

  void _updatePathSummary(_RouteResult routeResult) {
    int noSidewalk = 0;
    int unevenPath = 0;
    int obstruction = 0;

    for (final warning in routeResult.warnings) {
      final lower = warning.toLowerCase();
      if (lower.contains('sidewalk')) {
        noSidewalk += 1;
      }
      if (lower.contains('uneven') ||
          lower.contains('broken pavement') ||
          lower.contains('surface')) {
        unevenPath += 1;
      }
      if (lower.contains('obstacle') ||
          lower.contains('parked vehicle') ||
          lower.contains('vendor') ||
          lower.contains('construction') ||
          lower.contains('flooding') ||
          lower.contains('stairs') ||
          lower.contains('curb')) {
        obstruction += 1;
      }
    }

    final rating = (routeResult.accessibilityScore * 100).round().clamp(0, 100);
    final minutes = (routeResult.estimatedDurationSeconds / 60).ceil();
    _routeEtaLabel = "Estimated $minutes min walk";
    pathSummary = {
      "rating": rating,
      "obstaclesEncountered": {
        "noSidewalk": noSidewalk,
        "unevenPath": unevenPath,
        "obstruction": obstruction,
      }
    };
  }

  Future<_RouteResult> _calculateRoute(LatLng origin, LatLng destination) async {
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
      final accessibilityScore = (data['accessibility_score'] as num?)?.toDouble() ?? 0.0;
      final duration = (data['estimated_duration_seconds'] as num?)?.toInt() ?? 0;
      final distance = (data['distance_meters'] as num?)?.toDouble() ?? 0.0;
      final warnings = ((data['warnings'] as List?) ?? const [])
          .map((e) => e.toString())
          .toList();
      final coords = (data['coordinates'] as List).cast<dynamic>();
      final routeCoordinates = coords.map((p) {
        final arr = (p as List).cast<dynamic>();
        // Backend returns [Lon, Lat], LatLng needs [Lat, Lon]
        return LatLng((arr[1] as num).toDouble(), (arr[0] as num).toDouble());
      }).toList();
      final stepsJson = ((data['steps'] as List?) ?? const []).cast<dynamic>();
      final parsedSteps = <_NavigationStep>[];
      if (routeCoordinates.isNotEmpty) {
        for (var i = 0; i < stepsJson.length; i++) {
          final step = (stepsJson[i] as Map<String, dynamic>);
          final pointIndex =
              i < routeCoordinates.length ? i : routeCoordinates.length - 1;
          parsedSteps.add(
            _NavigationStep(
              distance: (step['distance'] as num?)?.toDouble() ?? 0.0,
              instruction: (step['instruction'] ?? '').toString(),
              pathCondition: (step['path_condition'] ?? 'unknown').toString(),
              point: routeCoordinates[pointIndex],
            ),
          );
        }
      }

      return _RouteResult(
        coordinates: routeCoordinates,
        accessibilityScore: accessibilityScore,
        estimatedDurationSeconds: duration,
        distanceMeters: distance,
        warnings: warnings,
        steps: parsedSteps,
      );
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
                  Text(_routeEtaLabel, style: TextStyle(color: Colors.grey[600], fontSize: 13)),
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
                _obstacleChip(Icons.do_not_disturb_on_rounded, "${obstacles['noSidewalk']} No Sidewalk"),
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

  List<Marker> _buildStepMarkers() {
    if (!_isNavigating || _navigationSteps.isEmpty) {
      return const [];
    }

    final markers = <Marker>[];
    for (var i = 0; i < _navigationSteps.length; i++) {
      if (!_shouldRenderStepMarker(i)) {
        continue;
      }
      final step = _navigationSteps[i];
      final isActive = i == _activeStepIndex;
      markers.add(
        Marker(
          point: step.point,
          width: 24,
          height: 24,
          child: Container(
            decoration: BoxDecoration(
              color: isActive ? Colors.orange : Colors.blue[700],
              shape: BoxShape.circle,
              border: Border.all(color: Colors.white, width: 2),
            ),
            child: Center(
              child: Text(
                '${i + 1}',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
        ),
      );
    }
    return markers;
  }

  bool _shouldRenderStepMarker(int index) {
    if (_navigationSteps.length <= 4) {
      return true;
    }

    final last = _navigationSteps.length - 1;
    if (index == 0 || index == last || index == _activeStepIndex) {
      return true;
    }

    // Keep immediate context around the current instruction visible.
    return (index - _activeStepIndex).abs() <= 1;
  }

  String _formatStepMeta(_NavigationStep step) {
    final meters = step.distance.round();
    return '${step.pathCondition} - ${meters}m';
  }

  void _nextStep() {
    if (_activeStepIndex >= _navigationSteps.length - 1) {
      return;
    }
    setState(() {
      _activeStepIndex += 1;
    });
    _mapController.move(_navigationSteps[_activeStepIndex].point, _navigationZoom);
  }

  void _finishNavigation() {
    setState(() {
      _isNavigating = false;
      _activeStepIndex = 0;
      _navigationSteps = [];
      routeLines = [];
      pointA = null;
      pointB = null;
    });
  }

  Future<void> _openQuickReport() async {
    final LatLng? reportPoint = _navigationSteps.isNotEmpty
        ? _navigationSteps[_activeStepIndex].point
        : pointA;
    if (reportPoint == null) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No active navigation point to report yet.')),
      );
      return;
    }

    final locationLabel =
        '${reportPoint.latitude.toStringAsFixed(6)}, ${reportPoint.longitude.toStringAsFixed(6)}';

    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ReportPage(
          currentIndex: 2,
          initialLatitude: reportPoint.latitude,
          initialLongitude: reportPoint.longitude,
          initialLocationLabel: locationLabel,
          captureOnOpen: true,
        ),
      ),
    );
  }

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
    final hasSteps = _navigationSteps.isNotEmpty;
    final safeIndex =
        _activeStepIndex < _navigationSteps.length ? _activeStepIndex : 0;
    final currentStep = hasSteps ? _navigationSteps[safeIndex] : null;
    final stepTitle =
        hasSteps ? 'STEP ${safeIndex + 1}/${_navigationSteps.length}' : 'NAVIGATING';
    final stepInstruction = currentStep?.instruction ?? 'Follow the blue path';
    final stepMeta =
        currentStep != null ? _formatStepMeta(currentStep) : 'route loaded';

    return Positioned(
      bottom: 30, // Floats above the bottom of the screen
      left: 20,
      right: 20,
      child: Container(
        height: 92,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        decoration: BoxDecoration(
          color: Colors.blue[800],
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.2),
              blurRadius: 15,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Row(
          children: [
            const Icon(Icons.navigation_rounded, color: Colors.white, size: 28),
            const SizedBox(width: 15),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    stepTitle,
                    style: const TextStyle(
                      color: Colors.white70,
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 1.2,
                    ),
                  ),
                  Text(
                    stepInstruction,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 15,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  Text(
                    stepMeta,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: Colors.white70, fontSize: 11),
                  ),
                ],
              ),
            ),
            if (hasSteps && _activeStepIndex < _navigationSteps.length - 1)
              IconButton(
                icon: const Icon(Icons.skip_next_rounded, color: Colors.white),
                onPressed: _nextStep,
              ),
            if (hasSteps && _activeStepIndex >= _navigationSteps.length - 1)
              IconButton(
                icon: const Icon(Icons.check_circle_rounded, color: Colors.white),
                onPressed: _finishNavigation,
              ),
            // CHANGE: Integrated Quick-Report shortcut for accessibility
            IconButton(
              icon: const Icon(Icons.add_a_photo_rounded, color: Colors.white),
              onPressed: _openQuickReport,
            ),
            const VerticalDivider(color: Colors.white24, indent: 15, endIndent: 15),
            IconButton(
              icon: const Icon(Icons.close_rounded, color: Colors.white),
              onPressed: _finishNavigation,
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
            mapController: _mapController,
            options: const MapOptions(
              initialCenter: LatLng(14.1675, 121.2431),
              initialZoom: _defaultZoom,
              maxZoom: 21.5,
              minZoom: 14,
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
                    child: Icon(
                      Icons.location_on,
                      color: Colors.green,
                      size: _isNavigating ? 30 : 40,
                    )
                  ),
                  if (pointB != null) Marker(
                    point: pointB!, 
                    child: Icon(
                      Icons.location_on,
                      color: Colors.red,
                      size: _isNavigating ? 30 : 40,
                    )
                  ),
                  ..._buildStepMarkers(),
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