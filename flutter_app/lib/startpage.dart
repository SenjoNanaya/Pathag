import 'package:flutter/material.dart';
import 'package:flutter_app/map_page.dart';

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
              errorBuilder: (context, error, StackTrace) {
                return const Icon(
                  Icons.map_outlined, 
                  size: 100, 
                  color: Colors.blue);
              },
            ),
            //const SizedBox(height: 20,),

            // === | TAGLINE | ===
            // const Text(
            //   'Pathag',
            //   style: TextStyle(
            //     fontSize: 32,
            //     fontWeight: FontWeight.bold,
            //     letterSpacing: 1.5
            //   ),
            // ),
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
                    Navigator.push(context, MaterialPageRoute(builder: (context) => MapPage()));
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
                    'TARA!',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold
                    ),
                  )
                ),
              ),
            )
          ],
        ),
      )
    );
  }
}