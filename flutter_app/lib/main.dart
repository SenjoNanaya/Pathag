import 'package:flutter/material.dart';
import 'package:flutter_app/screen/login.dart';
import 'package:flutter_app/screen/map_test.dart';
import 'package:flutter_app/screen/signup.dart';
import 'screen/app_shell.dart';
import '../screen/startpage.dart';


void main() {
  runApp(const MaterialApp(home: Pathag()));
}

class Pathag extends StatelessWidget {
  const Pathag({super.key});

  @override
  Widget build (BuildContext context) {
    return MaterialApp(
      title: 'Pathag: A People-Centric Navigation',
      theme: ThemeData(
        fontFamily: 'Helvetica',
        primaryColor: Colors.blue[800],
        scaffoldBackgroundColor: Colors.white
      ),
      initialRoute: '/',
      routes: {
        '/start-page': (context) => const StartPage(),
        '/login': (context) => const LoginPage(),
        '/sign-up': (context) => const SignUpPage(),
        '/navigation': (context) => const AppShell(initialIndex: 1),
        '/profile': (context) => const AppShell(initialIndex: 0),
        '/report-page': (context) => const AppShell(initialIndex: 2),
        '/map-test': (context) => const MapTest()

      },
      home: const StartPage()
      //home: const MapPage()
      //home: const MapTest()
    );
  }
}