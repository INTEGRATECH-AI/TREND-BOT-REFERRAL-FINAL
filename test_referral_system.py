#!/usr/bin/env python3
"""
Test script for LuxuryTrendBot referral system
"""

import sys
import os
sys.path.append('.')

from main_standalone import Database, User, Referral

def test_referral_system():
    """Test the referral system functionality"""
    print('🧪 Testing LuxuryTrendBot Referral System...')
    
    try:
        # Initialize database
        db = Database('test_referral.db')
        print('✅ Database initialized')
        
        # Create test users
        user1 = User(user_id=12345, username='testuser1', first_name='Alice')
        user2 = User(user_id=67890, username='testuser2', first_name='Bob', referred_by=user1.referral_code)
        
        # Save users
        db.save_user(user1)
        db.save_user(user2)
        print('✅ Test users created')
        print(f'   User 1 referral code: {user1.referral_code}')
        print(f'   User 2 referred by: {user2.referred_by}')
        
        # Create referral
        referral = Referral(
            referrer_code=user1.referral_code,
            referred_user_id=user2.user_id,
            reward_amount=5.0,
            status='confirmed'
        )
        db.save_referral(referral)
        print('✅ Referral created')
        
        # Test retrieval
        retrieved_user1 = db.get_user(12345)
        retrieved_user2 = db.get_user(67890)
        leaderboard = db.get_leaderboard(5)
        referrals = db.get_referrals(user1.referral_code)
        
        print(f'✅ User 1 referrals: {retrieved_user1.referral_count}')
        print(f'✅ User 1 earnings: ${retrieved_user1.total_earnings:.2f}')
        print(f'✅ User 2 referred by: {retrieved_user2.referred_by}')
        print(f'✅ Leaderboard entries: {len(leaderboard)}')
        print(f'✅ Referral records: {len(referrals)}')
        
        # Test referral link generation
        referral_link = f"https://t.me/LuxuryTrendBot?start={user1.referral_code}"
        print(f'✅ Referral link: {referral_link}')
        
        print('🎉 All referral system tests passed!')
        return True
        
    except Exception as e:
        print(f'❌ Test failed: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_referral_system()

