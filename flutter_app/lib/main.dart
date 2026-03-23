import 'package:flutter/material.dart';
import 'package:flutter_app/map_page.dart';
import '../startpage.dart';


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
        fontFamily: 'serif',
        primaryColor: Colors.blue[800]
      ),
      initialRoute: '/',
      routes: {
        '/start-page': (context) => const StartPage(),
        '/navigation': (context) => const MapPage()
      },
      home: const StartPage()
    );
  }
}