import 'package:flutter/material.dart';
import '../screen/login.dart';
import '../screen/signup.dart';

class StartPage extends StatefulWidget {
  const StartPage({super.key});

  @override
  State<StartPage> createState() => _StartPage();
}

class _StartPage extends State<StartPage> {
  @override
  Widget build (BuildContext context) {
    return Scaffold(
      body: Container(
        width: double.infinity,
        decoration: BoxDecoration(
          color: Colors.white
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Spacer(flex: 2,),

            // === | LOGO | ===
            Image.asset(
              'images/pathagLogo.png',
              width: 500,
              errorBuilder: (context, error, stackTrace) {
                return const Icon(
                  Icons.map_outlined, 
                  size: 100, 
                  color: Colors.blue);
              },
            ),

            const Text(
              'ano, tara?',
              style: TextStyle(
                fontSize: 16,
                color: Colors.grey,
                fontStyle: FontStyle.italic
              ),
            ),
            const Spacer(flex: 2,),

            // === | START BUTTON | ===
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 50),
              child: SizedBox(
                width: double.infinity,
                height: 55,
                child: ElevatedButton(
                  onPressed: () {
                    Navigator.push(context, MaterialPageRoute(builder: (context) => LoginPage()));
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.blue[800],
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(30)
                    ),
                    elevation: 5
                  ),
                  child: const Text(
                    'Login',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold
                    ),
                  )
                ),
              ),
            ),

            // === | SIGN-UP ROW | ===
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              //crossAxisAlignment: CrossAxisAlignment.center,
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
        ),
      )
    );
  }
}