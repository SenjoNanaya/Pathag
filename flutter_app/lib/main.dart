import 'package:flutter/material.dart';
import 'screen/map_page.dart';
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
        fontFamily: 'serif',
        primaryColor: Colors.blue[800]
      ),
      initialRoute: '/',
      routes: {
        '/start-page': (context) => const StartPage(),
        '/navigation': (context) => const MapPage()
      },
      home: const StartPage()
      //home: const MapPage()
    );
  }
}