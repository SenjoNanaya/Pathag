import 'package:flutter/material.dart';
import '../screen/map_page.dart';
import '../screen/signup.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPage();
}

class _LoginPage extends State<LoginPage> {
  final _formKey = GlobalKey<FormState>();
  String? email;
  String? password;
  bool rememberMe = false;

  @override
  Widget build (BuildContext context){
    return Scaffold(
      // appBar: AppBar(
      //   title: const Text(
      //     'Pathag Map'
      //   ),
      //   leading: IconButton(
      //     onPressed: () => Navigator.pop(context), 
      //     icon: const Icon(Icons.arrow_back_ios_new_outlined)
      //   ),
      // ),
      body: _buildBody()
    );
  }

  Widget _buildBody(){
    return Container (
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 30),
      decoration: BoxDecoration(color: Colors.white),
      child: Form (
        key: _formKey,
        child: Column (
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Spacer(flex: 2),

            // === | WELCOME TEXT | ===
            Text(
              'Welcome back',
              style: TextStyle(
                fontSize: 28,
                color: Colors.blue[800],
                fontWeight: FontWeight.bold
              )
            ),
            Text(
              'to Pathag!',
              style: TextStyle(
                fontSize: 28,
                color: Colors.blue[800],
                fontWeight: FontWeight.bold
              )
            ),
            const Spacer(flex:1),

            // === | EMAIL TEXT FIELD | ===
            TextFormField(
              keyboardType: TextInputType.emailAddress,
              decoration: InputDecoration(
                prefixIcon: Icon(Icons.email_outlined),
                border: OutlineInputBorder(),
                labelText: "Input Email"
              ),
              validator: (value) => (value == null || value.isEmpty) ? 'Required Field: Enter your Email' : null,
              onChanged: (value) => { email = value }
            ),
            const SizedBox(height: 20),

            // === | PASSWORD FIELD | ===
            TextFormField(
              obscureText: true,
              decoration: InputDecoration(
                prefixIcon: Icon(Icons.lock_outline_rounded),
                border: OutlineInputBorder(),
                labelText: "Input Password"
              ),
              validator: (value) => (value == null || value.isEmpty) ? 'Required Field: Enter your Password' : null,
              onChanged: (value) => { password = value }
            ),

            // === | REMEMBER & FORGOT | ===
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min, 
                  children: [
                    SizedBox(
                      height: 24,
                      width: 24,
                      child: Checkbox(
                        visualDensity: VisualDensity.compact, // Tightens the box
                        value: rememberMe,
                        onChanged: (value) {
                          setState(() {
                            rememberMe = value ?? false;
                          });
                        },
                      ),
                    ),
                    const SizedBox(width: 8), // Small controlled gap
                    const Text("Remember Me"),
                  ],
                ),

                TextButton(
                  onPressed: () {}, 
                  child: const Text('Forgot Password?')
                )
              ],
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
                      Navigator.push(context, MaterialPageRoute(builder: (context) => MapPage()));
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
                    'Login',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ),
              ),

              // === | SIGN-UP ROW | ===
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text("Don't have an account?"),
                  TextButton(
                    child: Text(
                      'Sign-up',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: Colors.blue[800]
                      )
                    ),
                    onPressed: () => {
                      Navigator.push(context, MaterialPageRoute(builder: (context) => SignUpPage()))
                    },
                  )
                ],
              ),
              const Spacer(flex: 1)
          ],
        )
      )
    );
  }
}