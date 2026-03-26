import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../widgets/custom_nav_bar.dart';

class ReportPage extends StatefulWidget {
  final int currentIndex;
  const ReportPage({super.key, this.currentIndex = 2});

  @override
  State<ReportPage> createState() => _ReportPage();
}

class _ReportPage extends State<ReportPage> {
  final _formKey = GlobalKey<FormState>();

  String? selectedCategory;
  final TextEditingController _locationController = TextEditingController();
  final TextEditingController _commentController = TextEditingController();
  File? _image;
  final ImagePicker _picker = ImagePicker();

  // PURPOSE: General Category
  final List<String> categories = [
    'Obstruction',
    'Path Surface Problem',
    'No Sidewalk',
  ];

  Future<void> _pickImage() async {
    final pickedFile = await _picker.pickImage(source: ImageSource.camera);
    if (pickedFile != null) {
      setState(() {
        _image = File(pickedFile.path);
      });
    }
  }

  void _submitReport() {
    if (_formKey.currentState!.validate() && selectedCategory != null) {
      // TODO: Logic to send to your Node.js/MongoDB backend
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Submitting Accessibility Report...')),
      );
    } else if (selectedCategory == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select a category')),
      );
    }
  }

  Widget _sectionHeader(String text) {
    return Text(
      text,
      style: TextStyle(
        fontWeight: FontWeight.bold, 
        fontSize: 16, 
        color: Colors.blue[800]),
    );
  }

  Widget _buildForm() {
    return Form (
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height:50),
          // == | TITLE | ==
          Text(
            'REPORT IMPEDIMENT',
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w900, 
              color: Colors.blue[800], 
              letterSpacing: 1.5,
            ),
          ),
          const Text(
            "help make the place more accessible by reporting barriers.",
            style: TextStyle(
              color: Colors.grey, 
              fontSize: 14,
              fontStyle: FontStyle.italic
            ),
          ),
          const SizedBox(height: 35),

          // == | UPLOAD PICTURE | ==
          _sectionHeader("EVIDENCE"),
          const SizedBox(height: 10),

          GestureDetector(
            onTap: _pickImage,
            child: Container(
              height: 200,
              width: double.infinity,
              decoration: BoxDecoration(
                color: Colors.grey[100],
                borderRadius: BorderRadius.circular(15),
                border: Border.all(color: Colors.grey[300]!),
              ),
              child: _image == null
                ? Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.camera_enhance_rounded, 
                        size: 45, 
                        color: Colors.blue[800]
                      ),
                      const SizedBox(height: 10),
                      const Text(
                        "Capture Micro-Impediment",
                        style: TextStyle(
                          color: Colors.grey, 
                          fontWeight: 
                          FontWeight.w500
                        )
                      ),
                    ],
                  )
                  : ClipRRect(
                    borderRadius: BorderRadius.circular(15),
                    child: Image.file(_image!, fit: BoxFit.cover),
                  ),
                ),
            ),
          const SizedBox(height: 25),

          // == | CATEGORIZE OBSTRUCTION | ==
          _sectionHeader("SELECT A CATEGORY"),
          const SizedBox(height: 10),

          Wrap(
            spacing: 8.0,
            children: categories.map((cat) {
              return ChoiceChip(
                label: Text(cat),
                selected: selectedCategory == cat,
                selectedColor: Colors.blue[800],
                backgroundColor: Colors.white,
                side: BorderSide.none,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                labelStyle: TextStyle(
                  fontWeight: FontWeight.bold,
                  color: selectedCategory == cat ? Colors.white : Colors.blue[800],
                ),
                onSelected: (selected) {
                  setState(() { selectedCategory = selected ? cat : null; });
                },
              );
            }).toList(),
          ),
          const SizedBox(height: 25),

          // == | LOCATION FIELD | ==
          _sectionHeader("LOCATION DETAILS"),
          const SizedBox(height: 10),

          TextFormField(
            controller: _locationController,
            decoration: InputDecoration(
              prefixIcon: const Icon(Icons.location_on_rounded, color: Colors.blueAccent),
              hintText: "e.g., Near Physci North Wing",
              hintStyle: const TextStyle(fontSize: 14, color: Colors.grey),
              filled: true,
              fillColor: Colors.grey[100],
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: BorderSide(color: Colors.grey[300]!)
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: BorderSide(color: Colors.grey[300]!)
              ), 
            ),
            validator: (value) => (value == null || value.isEmpty) ? 'Please describe where this is.' : null,
          ),
          const SizedBox(height: 20),

          // == | COMMENT (OPTIONAL) | ==
          _sectionHeader("ADDITIONAL NOTES"),
          const SizedBox(height: 10),

          TextFormField(
            controller: _commentController,
            maxLines: 3,
            decoration: InputDecoration(
              hintText: "Add a Comment or Short Description",
              hintStyle: const TextStyle(fontSize: 14, color: Colors.grey),
              filled: true,
              fillColor: Colors.grey[100],
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: BorderSide(color: Colors.grey[300]!)
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: BorderSide(color: Colors.grey[300]!)
              ), 
            ),
          ),
          const SizedBox(height: 40),

          // == | SUBMIT BUTTON | ==
          SizedBox(
            width: double.infinity,
            height: 55,
            child: ElevatedButton(
              onPressed: _submitReport,
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.blue[800],
                elevation: 0,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: const Text(
                'SUBMIT REPORT', 
                style: TextStyle(
                  fontSize: 16, 
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1.2
                )
              ),
            ),
          ),
          const SizedBox(height: 30)
        ],
      )
    ); 
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: _buildForm()
      ),
      bottomNavigationBar: CustomNavBar(selectedIndex: widget.currentIndex),
    );
  }
}