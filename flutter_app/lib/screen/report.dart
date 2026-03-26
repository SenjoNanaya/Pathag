import 'package:flutter/material.dart';
import 'dart:convert';
import 'dart:io';
import '../widgets/custom_nav_bar.dart';

class ReportPage extends StatefulWidget {
  final int currentIndex;
  const ReportPage({super.key, required this.currentIndex});

  @override
  State<ReportPage> createState() => _ReportPage();
}

class _ReportPage extends State<ReportPage> {
  static const String httpBaseUrl = 'http://localhost:8000';
  final _formKey = GlobalKey<FormState>();
  final TextEditingController _latController = TextEditingController(text: "14.1675");
  final TextEditingController _lonController = TextEditingController(text: "121.2431");
  final TextEditingController _descController = TextEditingController();
  final TextEditingController _reporterIdController = TextEditingController(text: "1");

  final List<String> _subtypes = const [
    "parked_vehicle",
    "vendor_stall",
    "construction",
    "flooding",
    "broken_pavement",
    "uneven_surface",
    "missing_curb_cut",
    "stairs_only",
    "other",
  ];
  final List<String> _reportKinds = const [
    "obstacle",
    "surface_problem",
    "environmental",
  ];

  String _selectedSubtype = "parked_vehicle";
  String _selectedReportKind = "obstacle";
  int _severity = 3;
  bool _isTemporary = true;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
  }

  @override
  void dispose() {
    _latController.dispose();
    _lonController.dispose();
    _descController.dispose();
    _reporterIdController.dispose();
    super.dispose();
  }

  Future<void> _submitReport() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    setState(() => _isSubmitting = true);

    try {
      final uri = Uri.parse('$httpBaseUrl/api/v1/obstacles/reports');
      final payload = {
        "reporter_id": int.parse(_reporterIdController.text),
        "latitude": double.parse(_latController.text),
        "longitude": double.parse(_lonController.text),
        "obstacle_type": "yes",
        "report_kind": _selectedReportKind,
        "report_subtype": _selectedSubtype,
        "subtype_source": "user",
        "description": _descController.text.trim().isEmpty ? null : _descController.text.trim(),
        "severity": _severity,
        "is_temporary": _isTemporary,
      };

      final client = HttpClient();
      final req = await client.postUrl(uri);
      req.headers.contentType = ContentType.json;
      req.write(jsonEncode(payload));
      final resp = await req.close();
      final body = await resp.transform(utf8.decoder).join();
      client.close(force: true);

      if (!mounted) return;
      if (resp.statusCode >= 200 && resp.statusCode < 300) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Report submitted successfully.")),
        );
        _descController.clear();
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Failed to submit report: HTTP ${resp.statusCode} $body")),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Failed to submit report: $e")),
      );
    } finally {
      if (mounted) {
        setState(() => _isSubmitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Form(
            key: _formKey,
            child: ListView(
              children: [
                Text(
                  "Create Obstacle Report",
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: Colors.blue[800],
                  ),
                ),
                const SizedBox(height: 16),
                TextFormField(
                  controller: _reporterIdController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    labelText: "Reporter ID",
                  ),
                  validator: (value) {
                    if (value == null || value.isEmpty) return "Required";
                    if (int.tryParse(value) == null) return "Must be a number";
                    return null;
                  },
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _latController,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    labelText: "Latitude",
                  ),
                  validator: (value) {
                    if (value == null || value.isEmpty) return "Required";
                    if (double.tryParse(value) == null) return "Must be a decimal";
                    return null;
                  },
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _lonController,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    labelText: "Longitude",
                  ),
                  validator: (value) {
                    if (value == null || value.isEmpty) return "Required";
                    if (double.tryParse(value) == null) return "Must be a decimal";
                    return null;
                  },
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: _selectedReportKind,
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    labelText: "Report Kind",
                  ),
                  items: _reportKinds
                      .map((value) => DropdownMenuItem(value: value, child: Text(value)))
                      .toList(),
                  onChanged: (value) {
                    if (value == null) return;
                    setState(() => _selectedReportKind = value);
                  },
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: _selectedSubtype,
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    labelText: "Subtype",
                  ),
                  items: _subtypes
                      .map((value) => DropdownMenuItem(value: value, child: Text(value)))
                      .toList(),
                  onChanged: (value) {
                    if (value == null) return;
                    setState(() => _selectedSubtype = value);
                  },
                ),
                const SizedBox(height: 12),
                Text("Severity: $_severity"),
                Slider(
                  value: _severity.toDouble(),
                  min: 1,
                  max: 5,
                  divisions: 4,
                  label: _severity.toString(),
                  onChanged: (value) => setState(() => _severity = value.round()),
                ),
                SwitchListTile(
                  value: _isTemporary,
                  title: const Text("Temporary hazard"),
                  onChanged: (value) => setState(() => _isTemporary = value),
                ),
                const SizedBox(height: 8),
                TextFormField(
                  controller: _descController,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    labelText: "Description (optional)",
                  ),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  height: 48,
                  child: ElevatedButton(
                    onPressed: _isSubmitting ? null : _submitReport,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.blue[800],
                      foregroundColor: Colors.white,
                    ),
                    child: Text(_isSubmitting ? "Submitting..." : "Submit Report"),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
      bottomNavigationBar: const CustomNavBar(selectedIndex: 2),
    );
  }
}