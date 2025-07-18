#!/usr/bin/env python3
"""
Quick email test script for restock bot
"""
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def test_email():
    # Load config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ config.json not found. Please create it first.")
        return
    
    try:
        # Create test email
        msg = MIMEMultipart()
        msg['From'] = config['email']['username']
        msg['To'] = config['email']['username']  # Send to yourself
        msg['Subject'] = "🧪 Restock Bot Email Test"
        
        body = """
        This is a test email from your restock bot!
        
        If you receive this, your email configuration is working correctly.
        
        ✅ SMTP connection: SUCCESS
        ✅ Authentication: SUCCESS
        ✅ Email sending: SUCCESS
        
        Your bot is ready to send restock notifications!
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        print("🔄 Sending test email...")
        with smtplib.SMTP(config['email']['smtp_server'], config['email']['smtp_port']) as server:
            server.starttls()
            server.login(config['email']['username'], config['email']['password'])
            server.send_message(msg)
        
        print("✅ Test email sent successfully!")
        print(f"📧 Check your inbox: {config['email']['username']}")
        
    except Exception as e:
        print(f"❌ Email test failed: {str(e)}")
        print("\nCommon issues:")
        print("1. Make sure you're using an App Password (not your regular Gmail password)")
        print("2. Check that 2-factor authentication is enabled on your Gmail account")
        print("3. Verify your email and password in config.json")

if __name__ == "__main__":
    test_email()