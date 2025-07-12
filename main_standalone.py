#!/usr/bin/env python3
"""
TrendBot - Cloud-Compatible Standalone Version
Automated Telegram Bot for Money Opportunities
Monetize The Internet 24/7
"""

import os
import sys
import asyncio
import logging
import random
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('trendbot.log')
    ]
)
log = logging.getLogger(__name__)

@dataclass
class Offer:
    """Data class for offers"""
    id: Optional[int] = None
    title: str = ""
    description: str = ""
    category: str = ""
    commission: float = 0.0
    gravity: Optional[float] = None
    affiliate_link: str = ""
    platform: str = ""
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

@dataclass
class User:
    """Data class for users with referral tracking"""
    id: Optional[int] = None
    user_id: int = 0
    username: str = ""
    first_name: str = ""
    referral_code: str = ""
    referred_by: Optional[str] = None
    referral_count: int = 0
    total_earnings: float = 0.0
    created_at: datetime = None
    last_active: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.last_active is None:
            self.last_active = datetime.now()
        if not self.referral_code:
            import secrets
            self.referral_code = f"LUX{secrets.token_hex(4).upper()}"

@dataclass
class Referral:
    """Data class for referral tracking"""
    id: Optional[int] = None
    referrer_code: str = ""
    referred_user_id: int = 0
    reward_amount: float = 0.0
    status: str = "pending"  # pending, confirmed, paid
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

class Database:
    """Simple database handler"""
    
    def __init__(self, db_path: str = "trendbot.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create offers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                commission REAL,
                gravity REAL,
                affiliate_link TEXT,
                platform TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create users table for referral tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                referral_code TEXT UNIQUE NOT NULL,
                referred_by TEXT,
                referral_count INTEGER DEFAULT 0,
                total_earnings REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create referrals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_code TEXT NOT NULL,
                referred_user_id INTEGER NOT NULL,
                reward_amount REAL DEFAULT 0.0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (referred_user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Create posts table for tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                offer_id INTEGER,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                channel_id TEXT,
                message_id INTEGER,
                FOREIGN KEY (offer_id) REFERENCES offers (id)
            )
        ''')
        
        conn.commit()
        conn.close()
        log.info("✅ Database initialized successfully")
    
    def save_offer(self, offer: Offer) -> int:
        """Save offer to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO offers (title, description, category, commission, gravity, affiliate_link, platform)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (offer.title, offer.description, offer.category, offer.commission, 
              offer.gravity, offer.affiliate_link, offer.platform))
        
        offer_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return offer_id
    
    def get_offers(self, limit: int = 10, category: str = None) -> List[Offer]:
        """Get offers from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if category:
            cursor.execute('''
                SELECT * FROM offers WHERE category = ? ORDER BY created_at DESC LIMIT ?
            ''', (category, limit))
        else:
            cursor.execute('''
                SELECT * FROM offers ORDER BY created_at DESC LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        offers = []
        for row in rows:
            offer = Offer(
                id=row[0], title=row[1], description=row[2], category=row[3],
                commission=row[4], gravity=row[5], affiliate_link=row[6], platform=row[7],
                created_at=datetime.fromisoformat(row[8]) if row[8] else datetime.now(),
                updated_at=datetime.fromisoformat(row[9]) if row[9] else datetime.now()
            )
            offers.append(offer)
        
        return offers
    
    def log_post(self, offer_id: int, channel_id: str, message_id: int):
        """Log posted message"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO posts (offer_id, channel_id, message_id)
            VALUES (?, ?, ?)
        ''', (offer_id, channel_id, message_id))
        
        conn.commit()
        conn.close()
    
    def save_user(self, user: User) -> int:
        """Save or update user in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute('SELECT id FROM users WHERE user_id = ?', (user.user_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing user
            cursor.execute('''
                UPDATE users SET username = ?, first_name = ?, last_active = ?
                WHERE user_id = ?
            ''', (user.username, user.first_name, datetime.now(), user.user_id))
            user_id = existing[0]
        else:
            # Insert new user
            cursor.execute('''
                INSERT INTO users (user_id, username, first_name, referral_code, referred_by)
                VALUES (?, ?, ?, ?, ?)
            ''', (user.user_id, user.username, user.first_name, user.referral_code, user.referred_by))
            user_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        return user_id
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by user_id"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return User(
                id=row[0], user_id=row[1], username=row[2], first_name=row[3],
                referral_code=row[4], referred_by=row[5], referral_count=row[6],
                total_earnings=row[7],
                created_at=datetime.fromisoformat(row[8]) if row[8] else datetime.now(),
                last_active=datetime.fromisoformat(row[9]) if row[9] else datetime.now()
            )
        return None
    
    def get_user_by_referral_code(self, referral_code: str) -> Optional[User]:
        """Get user by referral code"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE referral_code = ?', (referral_code,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return User(
                id=row[0], user_id=row[1], username=row[2], first_name=row[3],
                referral_code=row[4], referred_by=row[5], referral_count=row[6],
                total_earnings=row[7],
                created_at=datetime.fromisoformat(row[8]) if row[8] else datetime.now(),
                last_active=datetime.fromisoformat(row[9]) if row[9] else datetime.now()
            )
        return None
    
    def save_referral(self, referral: Referral) -> int:
        """Save referral to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO referrals (referrer_code, referred_user_id, reward_amount, status)
            VALUES (?, ?, ?, ?)
        ''', (referral.referrer_code, referral.referred_user_id, referral.reward_amount, referral.status))
        
        referral_id = cursor.lastrowid
        
        # Update referrer's referral count and earnings
        cursor.execute('''
            UPDATE users SET 
                referral_count = referral_count + 1,
                total_earnings = total_earnings + ?
            WHERE referral_code = ?
        ''', (referral.reward_amount, referral.referrer_code))
        
        conn.commit()
        conn.close()
        return referral_id
    
    def get_referrals(self, referrer_code: str) -> List[Referral]:
        """Get referrals for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM referrals WHERE referrer_code = ? ORDER BY created_at DESC
        ''', (referrer_code,))
        
        rows = cursor.fetchall()
        conn.close()
        
        referrals = []
        for row in rows:
            referral = Referral(
                id=row[0], referrer_code=row[1], referred_user_id=row[2],
                reward_amount=row[3], status=row[4],
                created_at=datetime.fromisoformat(row[5]) if row[5] else datetime.now(),
                updated_at=datetime.fromisoformat(row[6]) if row[6] else datetime.now()
            )
            referrals.append(referral)
        
        return referrals
    
    def get_leaderboard(self, limit: int = 10) -> List[User]:
        """Get top referrers leaderboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM users 
            WHERE referral_count > 0 
            ORDER BY referral_count DESC, total_earnings DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        users = []
        for row in rows:
            user = User(
                id=row[0], user_id=row[1], username=row[2], first_name=row[3],
                referral_code=row[4], referred_by=row[5], referral_count=row[6],
                total_earnings=row[7],
                created_at=datetime.fromisoformat(row[8]) if row[8] else datetime.now(),
                last_active=datetime.fromisoformat(row[9]) if row[9] else datetime.now()
            )
            users.append(user)
        
        return users

class OfferGenerator:
    """Generate realistic offers for all platforms"""
    
    def __init__(self):
        self.categories = ["make_money", "ai_tools", "crypto_airdrops", "newsletters", "gadgets"]
        self.platforms = ["ClickBank", "Digistore24", "SparkLoop", "beehiiv"]
    
    def generate_offers(self, count: int = 20) -> List[Offer]:
        """Generate realistic offers"""
        offers = []
        
        offer_templates = [
            # ClickBank Offers
            {
                "title": "AI Content Creator Pro",
                "description": "Revolutionary AI tool that creates viral content in seconds. Perfect for social media managers and content creators looking to scale their output.",
                "category": "ai_tools",
                "commission_range": (25, 97),
                "platform": "ClickBank",
                "gravity_range": (15, 85)
            },
            {
                "title": "Passive Income Blueprint 2025",
                "description": "Step-by-step system to build multiple passive income streams. Over 10,000 success stories from ordinary people making extraordinary money.",
                "category": "make_money",
                "commission_range": (47, 197),
                "platform": "ClickBank",
                "gravity_range": (20, 75)
            },
            {
                "title": "Crypto Trading Mastery",
                "description": "Professional crypto trading course that turned beginners into profitable traders. Includes live trading sessions and private Discord.",
                "category": "crypto_airdrops",
                "commission_range": (97, 297),
                "platform": "ClickBank",
                "gravity_range": (25, 90)
            },
            
            # Digistore24 Offers
            {
                "title": "Smart Home Revolution Kit",
                "description": "Complete smart home automation system with AI-powered controls. Transform your home into a futuristic living space.",
                "category": "gadgets",
                "commission_range": (15, 45),
                "platform": "Digistore24",
                "gravity_range": (10, 60)
            },
            {
                "title": "AI Business Automation Suite",
                "description": "All-in-one AI toolkit for automating your business operations. Includes chatbots, email automation, and customer service AI.",
                "category": "ai_tools",
                "commission_range": (67, 167),
                "platform": "Digistore24",
                "gravity_range": (30, 80)
            },
            {
                "title": "Digital Nomad Lifestyle Guide",
                "description": "Complete guide to building a location-independent business. Includes templates, tools, and step-by-step action plans.",
                "category": "make_money",
                "commission_range": (27, 87),
                "platform": "Digistore24",
                "gravity_range": (15, 70)
            },
            
            # SparkLoop Newsletter Offers
            {
                "title": "Crypto Millionaire Newsletter",
                "description": "Exclusive newsletter revealing crypto secrets that made ordinary people millionaires. Limited time access to insider strategies.",
                "category": "crypto_airdrops", 
                "commission_range": (3, 7),
                "platform": "SparkLoop",
                "gravity_range": (40, 95)
            },
            {
                "title": "AI Weekly Insider",
                "description": "Weekly newsletter covering the latest AI tools, trends, and money-making opportunities. Join 50,000+ subscribers.",
                "category": "ai_tools",
                "commission_range": (2, 6),
                "platform": "SparkLoop",
                "gravity_range": (35, 85)
            },
            {
                "title": "Side Hustle Success Stories",
                "description": "Weekly newsletter featuring real people making $1,000-$10,000+ monthly from side hustles. Includes actionable tips and strategies.",
                "category": "make_money",
                "commission_range": (4, 8),
                "platform": "SparkLoop",
                "gravity_range": (45, 90)
            },
            
            # beehiiv Newsletter Offers
            {
                "title": "The Entrepreneur's Edge",
                "description": "Daily newsletter with business insights from top entrepreneurs. Join 75,000+ subscribers getting exclusive content.",
                "category": "newsletters",
                "commission_range": (2, 5),
                "platform": "beehiiv",
                "gravity_range": (50, 95)
            },
            {
                "title": "Tech Trends Weekly",
                "description": "Weekly roundup of the hottest tech trends, gadgets, and innovations. Perfect for tech enthusiasts and early adopters.",
                "category": "gadgets",
                "commission_range": (1.5, 4),
                "platform": "beehiiv",
                "gravity_range": (30, 80)
            },
            {
                "title": "Morning Crypto Brief",
                "description": "Daily crypto market analysis and opportunities. Get the edge with insider insights and market predictions.",
                "category": "crypto_airdrops",
                "commission_range": (3, 6),
                "platform": "beehiiv",
                "gravity_range": (40, 85)
            }
        ]
        
        for i in range(count):
            template = random.choice(offer_templates)
            commission = random.uniform(*template["commission_range"])
            gravity = random.uniform(*template["gravity_range"])
            
            # Add some variation to titles
            title_variations = [
                template["title"],
                f"{template['title']} - Limited Time",
                f"🔥 {template['title']}",
                f"{template['title']} 2025 Edition"
            ]
            
            offer = Offer(
                title=random.choice(title_variations),
                description=template["description"],
                category=template["category"],
                commission=commission,
                gravity=gravity,
                affiliate_link=f"https://trendbot.link/{template['platform'].lower()}/{i+1}?ref=trendbot",
                platform=template["platform"]
            )
            offers.append(offer)
        
        return offers

class ContentGenerator:
    """Generate engaging content for posts"""
    
    def __init__(self):
        self.emojis = {
            "make_money": ["💰", "💵", "🤑", "💸", "🏆", "💎", "🚀"],
            "ai_tools": ["🤖", "⚡", "🚀", "💡", "🔥", "⭐", "🎯"],
            "crypto_airdrops": ["🪙", "💎", "🚀", "📈", "⭐", "🔥", "💰"],
            "newsletters": ["📧", "📰", "📊", "💌", "🎯", "📈", "⭐"],
            "gadgets": ["📱", "💻", "⌚", "🎧", "🔌", "🚀", "💡"]
        }
        
        self.hooks = [
            "🚨 MONEY OPPORTUNITY ALERT!",
            "💰 EXCLUSIVE DEAL DISCOVERED!",
            "🔥 TRENDING NOW - LIMITED TIME!",
            "⚡ INSTANT PROFIT OPPORTUNITY!",
            "🎯 HIGH-COMMISSION ALERT!",
            "💎 PREMIUM OPPORTUNITY FOUND!",
            "🚀 VIRAL MONEY-MAKER SPOTTED!"
        ]
        
        self.ctas = [
            "👆 CLICK TO CLAIM YOUR OPPORTUNITY",
            "🔗 TAP HERE TO START EARNING",
            "💰 CLICK NOW - LIMITED SPOTS",
            "⚡ INSTANT ACCESS - CLICK HERE",
            "🎯 CLAIM YOUR COMMISSION NOW",
            "🚀 START EARNING TODAY - CLICK",
            "💎 EXCLUSIVE ACCESS - TAP HERE"
        ]
    
    def generate_post(self, offer: Offer) -> str:
        """Generate engaging post content"""
        category_emojis = self.emojis.get(offer.category, ["🔥"])
        emoji = random.choice(category_emojis)
        hook = random.choice(self.hooks)
        cta = random.choice(self.ctas)
        
        # Platform-specific formatting
        if offer.platform in ["SparkLoop", "beehiiv"]:
            commission_text = f"💵 **Earn**: ${offer.commission:.2f} per subscriber"
        else:
            commission_text = f"💵 **Commission**: ${offer.commission:.2f}"
        
        # Category-specific descriptions
        urgency_phrases = [
            "⏰ *Limited time offer - Act fast!*",
            "🔥 *Trending now - Don't miss out!*",
            "⚡ *High demand - Secure your spot!*",
            "💎 *Exclusive access - Limited availability!*",
            "🚀 *Viral opportunity - Join now!*"
        ]
        
        post = f"{emoji} **{hook}** {emoji}\n\n"
        post += f"🎯 **{offer.title}**\n\n"
        post += f"{commission_text}\n"
        post += f"⭐ **Platform**: {offer.platform}\n"
        post += f"📈 **Category**: {offer.category.replace('_', ' ').title()}\n"
        
        if offer.gravity:
            post += f"🔥 **Popularity**: {offer.gravity:.0f}/100\n"
        
        post += f"\n{offer.description}\n\n"
        post += f"{cta}\n"
        post += f"🔗 {offer.affiliate_link}\n\n"
        post += random.choice(urgency_phrases)
        
        return post

class TrendBot:
    """Main TrendBot class - Cloud Compatible"""
    
    def __init__(self):
        self.db = Database()
        self.offer_generator = OfferGenerator()
        self.content_generator = ContentGenerator()
        self.app = None
        self.stats = {
            "posts_sent": 0,
            "offers_generated": 0,
            "bot_started": datetime.now()
        }
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with referral tracking"""
        user = update.effective_user
        
        # Extract referral code from command args
        referral_code = None
        if context.args and len(context.args) > 0:
            referral_code = context.args[0]
        
        # Get or create user
        existing_user = self.db.get_user(user.id)
        
        if not existing_user:
            # Create new user
            new_user = User(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or "",
                referred_by=referral_code
            )
            self.db.save_user(new_user)
            
            # Process referral if valid
            if referral_code:
                referrer = self.db.get_user_by_referral_code(referral_code)
                if referrer:
                    # Create referral record with reward
                    reward_amount = 5.0  # $5 reward per referral
                    referral = Referral(
                        referrer_code=referral_code,
                        referred_user_id=user.id,
                        reward_amount=reward_amount,
                        status="confirmed"
                    )
                    self.db.save_referral(referral)
                    
                    # Notify referrer
                    try:
                        await context.bot.send_message(
                            chat_id=referrer.user_id,
                            text=f"🎉 **New Referral!**\n\n"
                                 f"💎 {user.first_name or user.username or 'Someone'} joined using your referral link!\n"
                                 f"💰 You earned: ${reward_amount:.2f}\n"
                                 f"📊 Total referrals: {referrer.referral_count + 1}\n\n"
                                 f"Keep sharing to earn more! 🚀",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except:
                        pass  # User might have blocked the bot
            
            welcome_type = "new_with_referral" if referral_code else "new"
        else:
            # Update existing user activity
            existing_user.last_active = datetime.now()
            self.db.save_user(existing_user)
            welcome_type = "returning"
        
        # Get user's current stats
        current_user = self.db.get_user(user.id)
        
        if welcome_type == "new_with_referral":
            welcome_message = f"""
💎 **Welcome to LuxuryTrendBot!** 

🎉 **You were referred by a VIP member!**

I'm your premium automated money opportunity finder. I discover the most exclusive and high-paying opportunities:

💰 **Premium Affiliate Offers** - High-commission luxury products
📧 **Elite Newsletter Monetization** - Exclusive subscriber rewards  
🚀 **Cutting-Edge AI Tools** - Latest technology opportunities
💎 **Luxury Crypto Airdrops** - Premium blockchain opportunities

**🔥 REFERRAL PROGRAM:**
💸 Earn $5 for each person you refer!
🔗 Your referral link: https://t.me/LuxuryTrendBot?start={current_user.referral_code}
📊 Share and earn unlimited rewards!

**Commands:**
/referral - Get your referral link & stats
/leaderboard - See top earners
/help - Show all commands
/status - Check bot status

🎯 *I automatically post premium opportunities every 4 hours!*

💎 **Start earning luxury-level passive income today!**
            """
        elif welcome_type == "new":
            welcome_message = f"""
💎 **Welcome to LuxuryTrendBot!**

I'm your premium automated money opportunity finder. I discover the most exclusive and high-paying opportunities:

💰 **Premium Affiliate Offers** - High-commission luxury products
📧 **Elite Newsletter Monetization** - Exclusive subscriber rewards  
🚀 **Cutting-Edge AI Tools** - Latest technology opportunities
💎 **Luxury Crypto Airdrops** - Premium blockchain opportunities

**🔥 REFERRAL PROGRAM:**
💸 Earn $5 for each person you refer!
🔗 Your referral link: https://t.me/LuxuryTrendBot?start={current_user.referral_code}
📊 Share and earn unlimited rewards!

**Commands:**
/referral - Get your referral link & stats
/leaderboard - See top earners
/help - Show all commands
/status - Check bot status

🎯 *I automatically post premium opportunities every 4 hours!*

💎 **Start earning luxury-level passive income today!**
            """
        else:  # returning user
            welcome_message = f"""
💎 **Welcome back to LuxuryTrendBot!**

**Your Referral Stats:**
👥 Referrals: {current_user.referral_count}
💰 Earnings: ${current_user.total_earnings:.2f}
🔗 Your link: https://t.me/LuxuryTrendBot?start={current_user.referral_code}

**Quick Commands:**
/referral - Referral dashboard
/leaderboard - Top earners
/help - All commands

🎯 *Keep sharing to earn more rewards!*
            """
        
        await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = """
💎 **LuxuryTrendBot Help**

**🔥 REFERRAL COMMANDS:**
• `/referral` - Your referral dashboard & link
• `/leaderboard` - Top referrers leaderboard
• **Earn $5 per referral!** 💰

**📊 BOT COMMANDS:**
• `/start` - Welcome message
• `/help` - Show this help
• `/status` - Check bot status
• `/stats` - View statistics
• `/post` - Send test post to channel

**💸 REFERRAL PROGRAM:**
• Share your unique referral link
• Earn $5 for each person who joins
• Unlimited earning potential
• Instant rewards & notifications
• Climb the leaderboard for recognition

**Premium Features:**
• 🔄 Automatic luxury opportunity discovery
• 📊 Advanced performance tracking
• 💰 Premium revenue optimization
• 📱 Multi-platform elite support

**Exclusive Platforms:**
• **ClickBank Premium** - High-commission luxury affiliate offers
• **Digistore24 Elite** - Premium digital product commissions
• **SparkLoop VIP** - Exclusive newsletter monetization ($2-7/subscriber)
• **beehiiv Premium** - High-value newsletter growth opportunities

**Luxury Automation:**
• Posts every 4 hours automatically
• Smart premium offer rotation
• Category-based luxury content
• Advanced performance tracking

💎 *Bot runs 24/7 to maximize your luxury earning potential!*

🚀 **Use /referral to start earning immediately!**
        """
        await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        offers_count = len(self.db.get_offers(limit=1000))
        uptime = datetime.now() - self.stats["bot_started"]
        
        status_message = f"""
✅ **TrendBot Status**

🤖 **Bot**: Online and running
📊 **Database**: Connected
💾 **Offers Loaded**: {offers_count}
🔄 **Auto-posting**: Every 4 hours
📢 **Channel**: {TELEGRAM_CHANNEL_ID}
⏰ **Uptime**: {str(uptime).split('.')[0]}

**Performance:**
• Posts sent: {self.stats['posts_sent']}
• Offers generated: {self.stats['offers_generated']}

**Last Update**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🎯 *Everything is working perfectly!*
        """
        await update.message.reply_text(status_message, parse_mode=ParseMode.MARKDOWN)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        offers = self.db.get_offers(limit=1000)
        
        if not offers:
            await update.message.reply_text("📊 No statistics available yet. Generating offers...")
            return
        
        avg_commission = sum(offer.commission for offer in offers) / len(offers)
        platforms = {}
        categories = {}
        
        for offer in offers:
            platforms[offer.platform] = platforms.get(offer.platform, 0) + 1
            categories[offer.category] = categories.get(offer.category, 0) + 1
        
        stats_message = f"""
📊 **TrendBot Statistics**

💰 **Total Offers**: {len(offers)}
💵 **Average Commission**: ${avg_commission:.2f}
🏆 **Top Platform**: {max(platforms, key=platforms.get)}
🎯 **Top Category**: {max(categories, key=categories.get)}

**Platform Breakdown:**
"""
        for platform, count in platforms.items():
            stats_message += f"• {platform}: {count} offers\n"
        
        stats_message += f"""
**Category Breakdown:**
"""
        for category, count in categories.items():
            stats_message += f"• {category.replace('_', ' ').title()}: {count} offers\n"
        
        stats_message += f"\n**Revenue Potential**: ${avg_commission * len(offers):.2f}"
        stats_message += f"\n**Monthly Projection**: ${avg_commission * 30:.2f} (1 conversion/day)"
        
        await update.message.reply_text(stats_message, parse_mode=ParseMode.MARKDOWN)
    
    async def post_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /post command - send test post"""
        try:
            await self.post_to_channel()
            await update.message.reply_text("✅ Test post sent to channel!")
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to send post: {str(e)}")
    
    async def referral_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /referral command - show referral dashboard"""
        user = update.effective_user
        
        # Get or create user
        db_user = self.db.get_user(user.id)
        if not db_user:
            new_user = User(
                user_id=user.id,
                username=user.username or "",
                first_name=user.first_name or ""
            )
            self.db.save_user(new_user)
            db_user = self.db.get_user(user.id)
        
        # Get referral stats
        referrals = self.db.get_referrals(db_user.referral_code)
        
        referral_message = f"""
💎 **Your Referral Dashboard**

**📊 Your Stats:**
👥 **Total Referrals**: {db_user.referral_count}
💰 **Total Earnings**: ${db_user.total_earnings:.2f}
🏆 **Referral Code**: {db_user.referral_code}

**🔗 Your Referral Link:**
`https://t.me/LuxuryTrendBot?start={db_user.referral_code}`

**💸 How It Works:**
• Share your link with friends
• Earn $5 for each person who joins
• No limits - unlimited earning potential!
• Instant rewards when someone joins

**🚀 Sharing Tips:**
• Post in social media groups
• Share with entrepreneur friends
• Add to your email signature
• Include in your content

**Recent Referrals:**
"""
        
        if referrals:
            for i, referral in enumerate(referrals[:5]):  # Show last 5
                status_emoji = "✅" if referral.status == "confirmed" else "⏳"
                referral_message += f"{status_emoji} ${referral.reward_amount:.2f} - {referral.created_at.strftime('%m/%d')}\n"
        else:
            referral_message += "No referrals yet. Start sharing your link! 🚀"
        
        referral_message += f"\n💎 **Keep sharing to climb the leaderboard!**"
        
        await update.message.reply_text(referral_message, parse_mode=ParseMode.MARKDOWN)
    
    async def leaderboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /leaderboard command - show top referrers"""
        leaderboard = self.db.get_leaderboard(10)
        
        if not leaderboard:
            await update.message.reply_text(
                "🏆 **Referral Leaderboard**\n\n"
                "No referrers yet! Be the first to start earning! 🚀\n\n"
                "Use /referral to get your link and start climbing the leaderboard! 💎"
            )
            return
        
        leaderboard_message = "🏆 **Top Referrers - Leaderboard**\n\n"
        
        medals = ["🥇", "🥈", "🥉"]
        for i, user in enumerate(leaderboard):
            medal = medals[i] if i < 3 else f"{i+1}."
            name = user.first_name or user.username or "Anonymous"
            leaderboard_message += f"{medal} **{name}**\n"
            leaderboard_message += f"   👥 {user.referral_count} referrals | 💰 ${user.total_earnings:.2f}\n\n"
        
        leaderboard_message += "💎 **Want to be on the leaderboard?**\n"
        leaderboard_message += "Use /referral to get your link and start earning! 🚀"
        
        await update.message.reply_text(leaderboard_message, parse_mode=ParseMode.MARKDOWN)
    
    async def post_to_channel(self):
        """Post offer to channel"""
        try:
            # Get or generate offers
            offers = self.db.get_offers(limit=10)
            if not offers:
                log.info("No offers found, generating new ones...")
                new_offers = self.offer_generator.generate_offers(20)
                for offer in new_offers:
                    self.db.save_offer(offer)
                    self.stats["offers_generated"] += 1
                offers = new_offers[:10]
            
            # Select random offer
            offer = random.choice(offers)
            
            # Generate post content
            post_content = self.content_generator.generate_post(offer)
            
            # Send to channel
            message = await self.app.bot.send_message(
                chat_id=TELEGRAM_CHANNEL_ID,
                text=post_content,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Log the post
            self.db.log_post(offer.id, TELEGRAM_CHANNEL_ID, message.message_id)
            self.stats["posts_sent"] += 1
            
            log.info(f"✅ Posted offer to channel: {offer.title} (Commission: ${offer.commission:.2f})")
            
        except Exception as e:
            log.error(f"❌ Failed to post to channel: {e}")
    
    async def scheduled_posts(self, context: ContextTypes.DEFAULT_TYPE):
        """Scheduled posting job"""
        await self.post_to_channel()
    
    def start_bot(self):
        """Start the bot - cloud compatible"""
        if not TELEGRAM_BOT_TOKEN:
            log.error("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
            return
        
        if not TELEGRAM_CHANNEL_ID:
            log.error("❌ TELEGRAM_CHANNEL_ID not found in environment variables")
            return
        
        log.info("🚀 Starting TrendBot...")
        log.info("=" * 50)
        log.info("🤖 TrendBot | Monetize The Internet 24/7")
        log.info("=" * 50)
        
        # Initialize offers
        offers = self.db.get_offers(limit=1)
        if not offers:
            log.info("📦 Generating initial offers...")
            initial_offers = self.offer_generator.generate_offers(30)
            for offer in initial_offers:
                self.db.save_offer(offer)
                self.stats["offers_generated"] += 1
            log.info(f"✅ Generated {len(initial_offers)} initial offers")
        
        # Create application
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("post", self.post_command))
        self.app.add_handler(CommandHandler("referral", self.referral_command))
        self.app.add_handler(CommandHandler("leaderboard", self.leaderboard_command))
        
        # Schedule posts every 4 hours
        job_queue = self.app.job_queue
        job_queue.run_repeating(self.scheduled_posts, interval=14400, first=10)  # 4 hours = 14400 seconds
        
        log.info("✅ TrendBot started successfully!")
        log.info(f"📢 Posting to channel: {TELEGRAM_CHANNEL_ID}")
        log.info("🔄 Scheduled posts every 4 hours")
        log.info("💰 Revenue streams: ClickBank, Digistore24, SparkLoop, beehiiv")
        log.info("🎯 Ready to make money!")
        
        # Start polling - cloud compatible
        self.app.run_polling(drop_pending_updates=True)

def main():
    """Main entry point - cloud compatible"""
    try:
        log.info("🔥 Initializing TrendBot...")
        bot = TrendBot()
        bot.start_bot()
    except Exception as e:
        log.error(f"❌ Failed to start TrendBot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

