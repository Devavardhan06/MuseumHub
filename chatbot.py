import re
from datetime import date, datetime

# List of exhibits available in the museum
EXHIBITS = [
    "Dinosaur Sculpture", "Phoenix Bird", "Wooden Bicycle", "Dodo Bird", 
    "Black & White TV", "Lion Skull", "Nefertiti Bust", "Exakta Camera",
    "Arrau Turtle", "Amenemhat III", "Egyptian Coffins", "Daoist Immortal",
    "Roza Loewenfeld Bust", "Durga Goddess (10th Century)"
]

# Time slots available for booking
TIME_SLOTS = [
    "9AM–10AM", "10AM–11AM", "11AM–12PM", 
    "1PM–2PM", "2PM–3PM", "3PM–4PM"
]

# Enhanced patterns with more comprehensive responses
patterns = {
    # Greetings
    r'(hello|hi|hey|greetings)': "Hello! 👋 I'm your MuseumHub assistant. I can help you with:\n• Booking tickets\n• Information about exhibits\n• Time slots and availability\n• Museum policies\n• Navigation help\n\nWhat would you like to know?",
    
    # Booking related
    r'(book.*ticket|how.*book|reserve.*ticket|buy.*ticket|i.*want.*book|need.*ticket)': "I can help you book a ticket! 🎫\n\nHere's how:\n1. Tell me which date you'd like to visit (e.g., 'tomorrow' or '2024-12-20')\n2. I'll show you available time slots\n3. Choose your preferred time slot\n4. Tell me how many visitors\n5. I'll create the booking for you!\n\n💡 Example: 'I want to book for tomorrow at 10AM for 2 visitors'\n\nOr just say 'check availability for tomorrow' to see what's available!\n\nNote: You need to be logged in to complete bookings.",
    
    r'(time.*slot|available.*time|when.*open|hours|timing)': "We offer 6 time slots daily:\n• 9AM–10AM (Capacity: 20 visitors)\n• 10AM–11AM (Capacity: 25 visitors)\n• 11AM–12PM (Capacity: 25 visitors)\n• 1PM–2PM (Capacity: 30 visitors)\n• 2PM–3PM (Capacity: 30 visitors)\n• 3PM–4PM (Capacity: 20 visitors)\n\nThe museum is open daily. You can check real-time availability on the calendar page!",
    
    r'(availability|check.*available|slot.*available|is.*available|what.*available)': "I can check availability for you! 📅\n\nJust tell me the date:\n• 'Check availability for tomorrow'\n• 'What's available on 2024-12-20'\n• 'Show me slots for today'\n\nI'll show you all available time slots with remaining spots. Then you can book directly through me!\n\n💡 Try: 'check availability for tomorrow'",
    
    # Exhibits related
    r'(exhibit|exhibits|what.*see|what.*view|collection|artifacts|items|models)': f"We have {len(EXHIBITS)} amazing 3D exhibits! Here are some highlights:\n\n🏛️ Ancient Artifacts:\n• Nefertiti Bust (Ancient Egyptian)\n• Amenemhat III (Egyptian Pharaoh)\n• Egyptian Coffins\n• Durga Goddess (10th Century)\n\n🦕 Natural History:\n• Dinosaur Sculpture\n• Dodo Bird (Extinct)\n• Lion Skull\n• Arrau Turtle\n\n🎨 Art & Culture:\n• Phoenix Bird\n• Daoist Immortal\n• Roza Loewenfeld Bust\n\n📷 Vintage Items:\n• Exakta Camera\n• Black & White TV\n• Wooden Bicycle\n\nVisit the 'Explore Exhibits' page to view them in 3D!",
    
    r'(dinosaur|phoenix|nefertiti|egyptian|coffin|dodo|turtle|camera|bicycle|tv|skull|durga|daoist|amenemhat|roza)': "Great choice! We have that exhibit in our collection. You can view it in stunning 3D detail on our 'Explore Exhibits' page. Each exhibit can be rotated, zoomed, and explored interactively. Would you like to know more about any specific exhibit?",
    
    # Pricing
    r'(price|pricing|cost|fee|how.*much|ticket.*cost)': "Ticket pricing:\n• Standard ticket: Rs 100 per person\n• Children under 18: Not allowed (museum policy)\n• Group bookings: Same rate applies\n\nPayment can be made securely through our payment gateway. All bookings include access to all exhibits!",
    
    # Policies and guidelines
    r'(policy|policies|guidelines|rules|terms|conditions|cancel|refund)': "Important Museum Policies:\n\n1. Age Restriction: Visitors must be 18 years or older to book tickets\n2. Cancellation: Tickets can be cancelled within 48 hours of booking\n3. Multiple Bookings: Same person cannot book multiple tickets for the same time slot\n4. Refunds: Refunds are not available if you're unable to visit the museum after booking\n5. Time Slots: Please arrive on time for your selected slot\n6. Capacity: Each time slot has limited capacity - book early!\n\nNeed clarification on any policy?",
    
    r'(cancel.*booking|cancel.*ticket|how.*cancel)': "To cancel your booking:\n1. Log in to your account\n2. Go to 'My Bookings'\n3. Find your booking\n4. Click 'Cancel'\n\n⚠️ Remember: Cancellations must be made within 48 hours of booking to be eligible.",
    
    # Services
    r'(service|services|what.*offer|what.*do|features)': "MuseumHub offers:\n\n🎫 Ticket Booking System\n   • Easy online booking\n   • Real-time availability\n   • Multiple time slots\n\n👁️ 3D Exhibit Viewer\n   • Interactive 3D models\n   • Rotate and zoom exhibits\n   • Detailed descriptions\n\n🌐 Multilingual Support\n   • Choose your language\n   • English and French available\n\n🤖 AI Chatbot (that's me!)\n   • 24/7 assistance\n   • Booking help\n   • Exhibit information\n\nWhat service interests you most?",
    
    # Navigation help
    r'(how.*navigate|where.*go|how.*find|location|directions|where.*is)': "Navigation Guide:\n\n📅 To Book Tickets:\n   • Click 'Book Your Visit' on homepage\n   • Or visit /calendar\n\n👀 To View Exhibits:\n   • Click 'Explore Exhibits' on homepage\n   • Or visit /view\n\n💬 To Chat:\n   • You're already here! Just ask me anything\n\n🏠 Homepage:\n   • Visit / for main page\n\nNeed help finding something specific?",
    
    # Registration/Login
    r'(register|sign.*up|create.*account|new.*user|account)': "To create an account:\n1. Click 'Register' in the navigation\n2. Choose a username\n3. Set a password\n4. Submit the form\n\nAfter registration, you can:\n• Book tickets\n• View your bookings\n• Cancel bookings\n• Access all features\n\nAlready have an account? Just log in!",
    
    r'(login|sign.*in|log.*in)': "To log in:\n1. Click 'Login' in the navigation\n2. Enter your username and password\n3. Click 'Login'\n\nAfter logging in, you'll have access to:\n• Ticket booking\n• Your booking history\n• Account management\n\nNeed help with registration?",
    
    # General help
    r'(help|support|assistance|guide|how.*help)': "I'm here to help! I can assist with:\n\n✅ Ticket booking process\n✅ Exhibit information\n✅ Time slot availability\n✅ Museum policies\n✅ Navigation\n✅ Account management\n\nJust ask me anything! For example:\n• 'How do I book a ticket?'\n• 'What exhibits do you have?'\n• 'What are your time slots?'\n• 'How do I cancel a booking?'",
    
    # Goodbye
    r'(bye|goodbye|see.*you|thanks|thank.*you|thank.*bye)': "You're welcome! 😊\n\nIf you need any more help, just come back and chat with me. I'm here 24/7!\n\nEnjoy your visit to MuseumHub! 🏛️✨",
    
    # Contact
    r'(contact|email|phone|address|reach|get.*touch)': "For additional support:\n• Use this chatbot anytime (24/7)\n• Check the 'Contact' page for more options\n• Visit /contact for contact form\n\nI'm here to help with most questions though! What do you need?",
}

def get_chatbot_response(user_message):
    """
    Enhanced chatbot that provides helpful responses about ticket booking and exhibits.
    """
    if not user_message or not user_message.strip():
        return "Please ask me a question! I can help with booking tickets, exhibits, and more."
    
    user_message = user_message.lower().strip()
    
    # Check for specific exhibit names
    for exhibit in EXHIBITS:
        exhibit_lower = exhibit.lower()
        if exhibit_lower in user_message:
            return f"Great! We have the '{exhibit}' in our collection! 🎨\n\nYou can view it in stunning 3D detail on our 'Explore Exhibits' page. The 3D viewer allows you to:\n• Rotate the exhibit 360°\n• Zoom in for details\n• View from different angles\n\nWould you like to know about other exhibits or help with booking tickets?"
    
    # Check for time slot queries
    for slot in TIME_SLOTS:
        if slot.lower().replace('–', '-').replace('am', 'am').replace('pm', 'pm') in user_message:
            return f"The {slot} time slot is available for booking! 📅\n\nTo book this slot:\n1. Go to the Calendar page\n2. Select your preferred date\n3. Click on the date to see all available slots\n4. Choose {slot} and complete your booking\n\nEach slot has limited capacity, so book early to secure your spot!"
    
    # Check patterns
    for pattern, response in patterns.items():
        if re.search(pattern, user_message):
            return response
    
    # Default response with suggestions
    return "I'm not sure I understood that. 🤔\n\nI can help you with:\n• Booking tickets - ask 'How do I book a ticket?'\n• Exhibits - ask 'What exhibits do you have?'\n• Time slots - ask 'What time slots are available?'\n• Policies - ask 'What are your policies?'\n• Navigation - ask 'How do I navigate the site?'\n\nTry asking one of these questions, or rephrase your question!"
