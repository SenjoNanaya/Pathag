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
  final List<_RouteAlternativeResult> alternatives;

  _RouteResult({
    required this.coordinates,
    required this.accessibilityScore,
    required this.estimatedDurationSeconds,
    required this.distanceMeters,
    required this.warnings,
    required this.steps,
    required this.alternatives,
  });
}

class _RouteAlternativeResult {
  final List<LatLng> coordinates;
  final double accessibilityScore;
  final int estimatedDurationSeconds;
  final double distanceMeters;
  final List<String> warnings;
  final bool forceNotRecommended;
  final List<String> serverNotRecommendedReasons;
  final List<_NavigationStep> steps;

  _RouteAlternativeResult({
    required this.coordinates,
    required this.accessibilityScore,
    required this.estimatedDurationSeconds,
    required this.distanceMeters,
    required this.warnings,
    required this.forceNotRecommended,
    required this.serverNotRecommendedReasons,
    required this.steps,
  });
}

class _RouteIssueStats {
  final int blocked;
  final int noSidewalk;
  final int uneven;

  const _RouteIssueStats({
    required this.blocked,
    required this.noSidewalk,
    required this.uneven,
  });

  int get totalSevere => blocked + noSidewalk + uneven;
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
  final bool showNavBar;
  const MapPage({
    super.key,
    this.currentIndex = 1,
    this.showNavBar = true,
  });

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
  _RouteResult? _latestRouteResult;
  int _selectedRouteIndex = 0; // 0=Best, 1+=alternatives

  static const String _httpBaseUrl = "https://pathag-api.fly.dev";

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
      "obstruction": 0,
    }
  };
  String _routeEtaLabel = "Estimated -- mins walk";

  static const double _defaultZoom = 16.0;
  static const double _routeFocusZoom = 18.8;
  static const double _navigationZoom = 19.8;
  static const double _notRecommendedScoreGap = 0.05; // 5%

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

  List<Polyline> _buildSegmentPolylines(
    List<LatLng> coords,
    List<_NavigationStep> steps, {
    double opacity = 1.0,
    double strokeWidth = 6.0,
  }) {
    if (coords.length < 2) {
      return const [];
    }

    // Route steps are per segment plus a final "arrived" step.
    // Color each segment using the matching step's path condition.
    final polylines = <Polyline>[];
    final segmentCount = coords.length - 1;
    for (var i = 0; i < segmentCount; i++) {
      final stepCondition = (i < steps.length)
          ? steps[i].pathCondition
          : 'smooth';
      polylines.add(
        Polyline(
          points: [coords[i], coords[i + 1]],
          color: _segmentColor(stepCondition).withValues(alpha: opacity),
          strokeWidth: strokeWidth,
        ),
      );
    }
    return polylines;
  }

  List<Polyline> _buildRoutePolylines(
    _RouteResult routeResult, {
    int selectedIndex = 0,
  }) {
    final polylines = <Polyline>[];
    final allRoutes = _allRoutes(routeResult);

    for (var i = 0; i < allRoutes.length; i++) {
      final route = allRoutes[i];
      final isSelected = i == selectedIndex;
      polylines.addAll(
        _buildSegmentPolylines(
          route.coordinates,
          route.steps,
          opacity: isSelected ? 1.0 : 0.35,
          strokeWidth: isSelected ? 6.0 : 4.0,
        ),
      );
    }
    return polylines;
  }

  List<_RouteAlternativeResult> _allRoutes(_RouteResult routeResult) {
    return <_RouteAlternativeResult>[
      _RouteAlternativeResult(
        coordinates: routeResult.coordinates,
        accessibilityScore: routeResult.accessibilityScore,
        estimatedDurationSeconds: routeResult.estimatedDurationSeconds,
        distanceMeters: routeResult.distanceMeters,
        warnings: routeResult.warnings,
        forceNotRecommended: false,
        serverNotRecommendedReasons: const [],
        steps: routeResult.steps,
      ),
      ...routeResult.alternatives,
    ];
  }

  _RouteIssueStats _issueStatsForSteps(List<_NavigationStep> steps) {
    var blocked = 0;
    var noSidewalk = 0;
    var uneven = 0;
    for (final step in steps) {
      final condition = step.pathCondition.toLowerCase();
      if (condition == 'obstructed') {
        blocked += 1;
      } else if (condition == 'no_sidewalk') {
        noSidewalk += 1;
      } else if (condition == 'uneven' || condition == 'cracked') {
        uneven += 1;
      }
    }
    return _RouteIssueStats(
      blocked: blocked,
      noSidewalk: noSidewalk,
      uneven: uneven,
    );
  }

  bool _isRouteNotRecommended({
    required _RouteAlternativeResult best,
    required _RouteAlternativeResult candidate,
  }) {
    if (candidate.forceNotRecommended) {
      return true;
    }
    final scoreGap = best.accessibilityScore - candidate.accessibilityScore;
    final bestStats = _issueStatsForSteps(best.steps);
    final candidateStats = _issueStatsForSteps(candidate.steps);
    return scoreGap >= _notRecommendedScoreGap ||
        candidateStats.totalSevere > bestStats.totalSevere;
  }

  List<String> _notRecommendedReasons({
    required _RouteAlternativeResult best,
    required _RouteAlternativeResult candidate,
  }) {
    if (candidate.forceNotRecommended &&
        candidate.serverNotRecommendedReasons.isNotEmpty) {
      return candidate.serverNotRecommendedReasons;
    }
    final reasons = <String>[];
    final bestStats = _issueStatsForSteps(best.steps);
    final candidateStats = _issueStatsForSteps(candidate.steps);

    final blockedDelta = candidateStats.blocked - bestStats.blocked;
    if (blockedDelta > 0) {
      reasons.add('+$blockedDelta blocked segments');
    }

    final noSidewalkDelta = candidateStats.noSidewalk - bestStats.noSidewalk;
    if (noSidewalkDelta > 0) {
      reasons.add('+$noSidewalkDelta no-sidewalk segments');
    }

    final unevenDelta = candidateStats.uneven - bestStats.uneven;
    if (unevenDelta > 0) {
      reasons.add('+$unevenDelta uneven segments');
    }

    final scoreGap = best.accessibilityScore - candidate.accessibilityScore;
    if (scoreGap >= _notRecommendedScoreGap) {
      final scoreDropPercent = (scoreGap * 100).round();
      reasons.add('-$scoreDropPercent% accessibility');
    }

    final minutesDelta =
        ((candidate.estimatedDurationSeconds - best.estimatedDurationSeconds) / 60)
            .ceil();
    if (minutesDelta > 0) {
      reasons.add('+$minutesDelta min longer');
    }

    if (reasons.isEmpty) {
      reasons.add('Lower overall route quality than Best');
    }
    return reasons;
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
        setState(() {
          _latestRouteResult = routeResult;
          _selectedRouteIndex = 0;
          _applySelectedRoute(routeIndex: 0);
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
      _selectedRouteIndex = 0;
      _latestRouteResult = null;
      pointA = null;
      pointB = null;
      _isNavigating = false;
    });
    Navigator.pop(context);
  }

  // == | ROUTE CALCULATION | ==

  void _updatePathSummaryFromRoute({
    required double accessibilityScore,
    required int estimatedDurationSeconds,
    required List<_NavigationStep> steps,
    required List<String> warnings,
  }) {
    int noSidewalk = 0;
    int unevenPath = 0;
    int obstruction = 0;

    // Count segment issues from step path labels (ground truth for drawn route),
    // not from free-text warnings which may include nearby/non-segment context.
    for (final step in steps) {
      final condition = step.pathCondition.toLowerCase();
      if (condition == 'uneven' || condition == 'cracked') {
        unevenPath += 1;
      } else if (condition == 'no_sidewalk') {
        noSidewalk += 1;
      } else if (condition == 'obstructed') {
        obstruction += 1;
      }
    }

    // Keep warning parsing only as a fallback when route steps are unavailable.
    if (steps.isEmpty) {
      for (final warning in warnings) {
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
    }

    final rating = (accessibilityScore * 100).round().clamp(0, 100);
    final minutes = (estimatedDurationSeconds / 60).ceil();
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

  void _applySelectedRoute({required int routeIndex}) {
    final routeResult = _latestRouteResult;
    if (routeResult == null) {
      return;
    }
    final allRoutes = _allRoutes(routeResult);
    if (routeIndex < 0 || routeIndex >= allRoutes.length) {
      return;
    }

    final selected = allRoutes[routeIndex];
    _selectedRouteIndex = routeIndex;
    _navigationSteps = selected.steps;
    _activeStepIndex = 0;
    routeLines = _buildRoutePolylines(routeResult, selectedIndex: routeIndex);
    _updatePathSummaryFromRoute(
      accessibilityScore: selected.accessibilityScore,
      estimatedDurationSeconds: selected.estimatedDurationSeconds,
      steps: selected.steps,
      warnings: selected.warnings,
    );
    if (selected.coordinates.isNotEmpty) {
      _mapController.move(selected.coordinates.first, _routeFocusZoom);
    }
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
      List<_NavigationStep> parseSteps(
        List<dynamic> stepsJson,
        List<LatLng> coordinatesForSteps,
      ) {
        final parsed = <_NavigationStep>[];
        if (coordinatesForSteps.isEmpty) {
          return parsed;
        }
        for (var i = 0; i < stepsJson.length; i++) {
          final step = (stepsJson[i] as Map<String, dynamic>);
          final pointIndex =
              i < coordinatesForSteps.length ? i : coordinatesForSteps.length - 1;
          parsed.add(
            _NavigationStep(
              distance: (step['distance'] as num?)?.toDouble() ?? 0.0,
              instruction: (step['instruction'] ?? '').toString(),
              pathCondition: (step['path_condition'] ?? 'unknown').toString(),
              point: coordinatesForSteps[pointIndex],
            ),
          );
        }
        return parsed;
      }

      final parsedSteps = parseSteps(
        ((data['steps'] as List?) ?? const []).cast<dynamic>(),
        routeCoordinates,
      );

      final alternativesJson =
          ((data['alternative_routes'] as List?) ?? const []).cast<dynamic>();
      final alternatives = <_RouteAlternativeResult>[];
      for (final rawAlt in alternativesJson) {
        final alt = (rawAlt as Map<String, dynamic>);
        final altCoordsRaw = ((alt['coordinates'] as List?) ?? const []).cast<dynamic>();
        final altCoords = altCoordsRaw.map((p) {
          final arr = (p as List).cast<dynamic>();
          return LatLng((arr[1] as num).toDouble(), (arr[0] as num).toDouble());
        }).toList();
        final altSteps = parseSteps(
          ((alt['steps'] as List?) ?? const []).cast<dynamic>(),
          altCoords,
        );
        alternatives.add(
          _RouteAlternativeResult(
            coordinates: altCoords,
            accessibilityScore:
                (alt['accessibility_score'] as num?)?.toDouble() ?? 0.0,
            estimatedDurationSeconds:
                (alt['estimated_duration_seconds'] as num?)?.toInt() ?? 0,
            distanceMeters: (alt['distance_meters'] as num?)?.toDouble() ?? 0.0,
            warnings: ((alt['warnings'] as List?) ?? const [])
                .map((e) => e.toString())
                .toList(),
            forceNotRecommended:
                (alt['force_not_recommended'] as bool?) ?? false,
            serverNotRecommendedReasons:
                ((alt['not_recommended_reasons'] as List?) ?? const [])
                    .map((e) => e.toString())
                    .toList(),
            steps: altSteps,
          ),
        );
      }

      return _RouteResult(
        coordinates: routeCoordinates,
        accessibilityScore: accessibilityScore,
        estimatedDurationSeconds: duration,
        distanceMeters: distance,
        warnings: warnings,
        steps: parsedSteps,
        alternatives: alternatives,
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
      builder: (context) => StatefulBuilder(
        builder: (context, modalSetState) => _buildPathSummary(
          onSelectRoute: (index) {
            setState(() => _applySelectedRoute(routeIndex: index));
            modalSetState(() {});
          },
        ),
      ),
    );
  }

  Widget _buildPathSummary({required ValueChanged<int> onSelectRoute}) {
    final obstacles = pathSummary["obstaclesEncountered"];
    final routeResult = _latestRouteResult;
    final routeCount = routeResult == null ? 0 : (1 + routeResult.alternatives.length);
    final allRoutes = routeResult == null ? <_RouteAlternativeResult>[] : _allRoutes(routeResult);
    final hasBestAndSelected = allRoutes.isNotEmpty && _selectedRouteIndex < allRoutes.length;
    final bestRoute = hasBestAndSelected ? allRoutes[0] : null;
    final selectedRoute = hasBestAndSelected ? allRoutes[_selectedRouteIndex] : null;
    final showNotRecommended = bestRoute != null &&
        selectedRoute != null &&
        _selectedRouteIndex > 0 &&
        _isRouteNotRecommended(best: bestRoute, candidate: selectedRoute);
    final notRecommendedReasons = showNotRecommended
        ? _notRecommendedReasons(best: bestRoute, candidate: selectedRoute)
        : const <String>[];
    
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

          if (routeCount > 1) ...[
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: List.generate(routeCount, (index) {
                  final label = index == 0 ? "Best" : "Alt $index";
                  final selected = _selectedRouteIndex == index;
                  final route = allRoutes[index];
                  final best = allRoutes[0];
                  final notRecommended = index > 0 &&
                      _isRouteNotRecommended(best: best, candidate: route);
                  return Padding(
                    padding: EdgeInsets.only(right: index == routeCount - 1 ? 0 : 8),
                    child: ChoiceChip(
                      label: Text(notRecommended ? "$label (Not Recommended)" : label),
                      selected: selected,
                      onSelected: (_) => onSelectRoute(index),
                      selectedColor: selected
                          ? (notRecommended ? Colors.red[700] : Colors.blue[800])
                          : null,
                      side: notRecommended
                          ? BorderSide(color: Colors.red[300]!, width: 1)
                          : null,
                      labelStyle: TextStyle(
                        color: selected
                            ? Colors.white
                            : (notRecommended ? Colors.red[700] : Colors.blue[900]),
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  );
                }),
              ),
            ),
            const SizedBox(height: 16),
          ],

          if (showNotRecommended) ...[
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.red[50],
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.red[100]!),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    "Not Recommended",
                    style: TextStyle(
                      color: Colors.red[800],
                      fontWeight: FontWeight.w800,
                      fontSize: 13,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    "Why not recommended",
                    style: TextStyle(
                      color: Colors.red[700],
                      fontWeight: FontWeight.w700,
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: notRecommendedReasons
                        .map(
                          (reason) => Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 10,
                              vertical: 6,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(999),
                              border: Border.all(color: Colors.red[100]!),
                            ),
                            child: Text(
                              reason,
                              style: TextStyle(
                                color: Colors.red[800],
                                fontSize: 12,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        )
                        .toList(),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
          ],

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
          showNavBar: false,
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
      bottomNavigationBar: (widget.showNavBar && !_isNavigating)
          ? CustomNavBar(selectedIndex: widget.currentIndex)
          : null,
    );
  }
}