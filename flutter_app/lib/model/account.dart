import 'package:latlong2/latlong.dart';

class Account {
  // === | ACCOUNT DETAILS | ===
  String username;
  String email;
  String password;
  String region;

  // === | ACCESSIBILITY PROFILE | ===
  String accessibility;

  // === | NAVIGATION ATTRIBUTES | ===
  LatLng pointA;
  LatLng pointB;
  LatLng currentLoc;
  LatLng totalDistance;

  Account(this.username, this.email, this.password, this.region,
          this.accessibility, 
          this.pointA, this.pointB, this.currentLoc, this.totalDistance
  );
}