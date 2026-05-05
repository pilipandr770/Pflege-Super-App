#!/bin/bash

BASE_URL="http://localhost:5000"
COOKIE_JAR="cookies.txt"

# Get CSRF token from login page
echo "1. Getting CSRF token from login page..."
LOGIN_PAGE=$(curl -s -c "$COOKIE_JAR" "$BASE_URL/auth/login")
CSRF_TOKEN=$(echo "$LOGIN_PAGE" | grep -oP 'name="csrf_token" value="\K[^"]+')
echo "   CSRF Token: ${CSRF_TOKEN:0:20}..."

# Try to login with test credentials
echo "2. Attempting login with doctor@test.de..."
LOGIN_RESPONSE=$(curl -s -b "$COOKIE_JAR" -c "$COOKIE_JAR" -X POST "$BASE_URL/auth/login" \
  -d "email=doctor@test.de&password=test123&csrf_token=$CSRF_TOKEN" \
  -L)

# Check if login was successful
if echo "$LOGIN_RESPONSE" | grep -q "Medikamente\|Patienten\|Dashboard"; then
  echo "   ✓ Login successful"
  
  # Get list of patients
  echo "3. Fetching patient list..."
  PATIENTS_PAGE=$(curl -s -b "$COOKIE_JAR" "$BASE_URL/patients")
  
  # Extract first patient ID
  PATIENT_ID=$(echo "$PATIENTS_PAGE" | grep -oP 'patients/show/\K[0-9]+' | head -1)
  
  if [ -n "$PATIENT_ID" ]; then
    echo "   ✓ Found patient ID: $PATIENT_ID"
    
    echo "4. Accessing patient medications page..."
    MED_PAGE=$(curl -s -b "$COOKIE_JAR" "$BASE_URL/medications/patient/$PATIENT_ID")
    
    if echo "$MED_PAGE" | grep -q "Medikamente"; then
      echo "   ✓ Accessed medications page"
      
      # Check if Dokumente button exists
      if echo "$MED_PAGE" | grep -q "Dokumente\|documents"; then
        echo "   ✓ Found Dokumente button - document feature is visible!"
      else
        echo "   ✗ Dokumente button not found"
      fi
    fi
  fi
else
  echo "   ✗ Login failed or test user doesn't exist"
  echo "   Checking what users are available..."
fi

