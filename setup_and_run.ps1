# F3000 Power Monitor Setup
# Set your credentials here, then run: python f3000_power_simple.py

# Set environment variables (replace with your actual credentials)
$env:ANKERUSER = "wayne.ledrew@tech-method.com"
$env:ANKERPASSWORD = "your_password_here"  # Replace with your actual password
$env:ANKERCOUNTRY = "CA"

Write-Host "✅ Environment variables set!" -ForegroundColor Green
Write-Host "Now run: python f3000_power_simple.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "Or run both commands at once:" -ForegroundColor Cyan  
Write-Host "python f3000_power_simple.py" -ForegroundColor White