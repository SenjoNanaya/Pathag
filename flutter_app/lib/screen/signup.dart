import 'package:flutter/material.dart';
import 'package:flutter_app/screen/login.dart';
import 'package:flutter_app/screen/map_page.dart';

class SignUpPage extends StatefulWidget {
  const SignUpPage({super.key});

  @override
  State<SignUpPage> createState() => _SignUpPage();
}

class _SignUpPage extends State<SignUpPage> {
  final _formKey = GlobalKey<FormState>();
  String? email;
  String? password;
  String? username;
  String? region;
  bool rememberMe = false;

  static final List<String> _regions = ["MIMAROPA", "NCR", "Region IV-A"];
  String _selectedRegion = "MIMAROPA";

  @override
  Widget build(BuildContext context) {
    return Scaffold(body: _buildBody());
  }

  Widget _buildBody() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 30),
      decoration: BoxDecoration(color: Colors.white),
      child: Form(
        key: _formKey,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Spacer(flex: 2),

            // === | WELCOME TEXT | ===
            Text(
              'Welcome back',
              style: TextStyle(
                fontSize: 28,
                color: Colors.blue[800],
                fontWeight: FontWeight.bold,
              ),
            ),
            Text(
              'to Pathag!',
              style: TextStyle(
                fontSize: 28,
                color: Colors.blue[800],
                fontWeight: FontWeight.bold,
              ),
            ),
            const Spacer(flex: 1),

            // === | EMAIL TEXT FIELD | ===
            TextFormField(
              keyboardType: TextInputType.emailAddress,
              decoration: InputDecoration(
                prefixIcon: Icon(Icons.email_outlined),
                border: OutlineInputBorder(),
                labelText: "Input Email",
              ),
              validator: (value) => (value == null || value.isEmpty)
                  ? 'Required Field: Enter your Email'
                  : null,
              onChanged: (value) => {email = value},
            ),
            const SizedBox(height: 20),

            // === | PASSWORD FIELD | ===
            TextFormField(
              obscureText: true,
              decoration: InputDecoration(
                prefixIcon: Icon(Icons.lock_outline_rounded),
                border: OutlineInputBorder(),
                labelText: "Input Password",
              ),
              validator: (value) => (value == null || value.isEmpty)
                  ? 'Required Field: Enter your Password'
                  : null,
              onChanged: (value) => {password = value},
            ),

            const SizedBox(height: 20),

            // === | USERNAME TEXT FIELD | ===
            TextFormField(
              keyboardType: TextInputType.emailAddress,
              decoration: InputDecoration(
                prefixIcon: Icon(Icons.email_outlined),
                border: OutlineInputBorder(),
                labelText: "Input Email",
              ),
              validator: (value) => (value == null || value.isEmpty)
                  ? 'Required Field: Enter your Email'
                  : null,
              onChanged: (value) => {email = value},
            ),
            const SizedBox(height: 20),

            // === | REGION FIELD | ===
            DropdownButtonFormField<String>(
              value: _selectedRegion, // current selected value
              items: _regions.map((weather) {
                return DropdownMenuItem<String>(
                  value: weather,
                  child: Text(weather),
                );
              }).toList(), // convert Iterable to List
              onChanged: (value) {
                setState(() {
                  _selectedRegion = value!;
                });
              },
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Required';
                }
                return null;
              },
            ),

            const Spacer(flex: 2),

            // === | LOGIN BUTTON | ===
            SizedBox(
              width: double.infinity,
              height: 55,
              child: ElevatedButton(
                onPressed: () {
                  // 5. Trigger validation logic
                  if (_formKey.currentState!.validate()) {
                    print("Logging in with $email");
                    Navigator.push(
                      context,
                      MaterialPageRoute(builder: (context) => MapPage()),
                    );
                  }
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.blue[800],
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(30),
                  ),
                  elevation: 5,
                ),
                child: const Text(
                  'Create Account',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ),
            ),

            // === | SIGN-UP ROW | ===
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text("Already have an account?"),
                TextButton(
                  child: Text(
                    'Log-in',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: Colors.blue[800],
                    ),
                  ),
                  onPressed: () => {
                    Navigator.push(
                      context,
                      MaterialPageRoute(builder: (context) => LoginPage()),
                    ),
                  },
                ),
              ],
            ),
            const Spacer(flex: 1),
          ],
        ),
      ),
    );
  }
}
