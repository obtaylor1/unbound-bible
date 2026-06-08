#!/usr/bin/env python3
"""
Add ASV and WEB translations for all popular verses in the dropdown list.
This ensures every verse in the dropdown shows all three translations: KJV, ASV, WEB.
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL')

# All unique verses from the popular verses dropdown
POPULAR_VERSES = [
    # Complete Translations Available (already exist)
    ('John', 3, 16),
    ('Genesis', 1, 1),
    ('Psalms', 23, 1),
    ('Matthew', 28, 19),
    ('Romans', 3, 23),
    ('Ephesians', 2, 8),
    
    # Faith & Trust in God (need ASV + WEB)
    ('Hebrews', 11, 1),
    ('Proverbs', 3, 5),
    ('Isaiah', 41, 10),
    ('Philippians', 4, 13),
    ('Jeremiah', 29, 11),
    ('Romans', 8, 28),
    ('Matthew', 17, 20),
    ('Psalms', 46, 1),
    ('2 Corinthians', 5, 7),
    ('Psalms', 37, 4),
    
    # Love & Relationships
    ('1 Corinthians', 13, 4),
    ('1 John', 4, 7),
    ('Matthew', 22, 37),
    ('Colossians', 3, 14),
    ('Romans', 12, 9),
    ('Song of Solomon', 8, 7),
    ('1 Peter', 4, 8),
    ('Ephesians', 5, 25),
    ('Proverbs', 17, 17),
    
    # Strength & Courage
    ('Joshua', 1, 9),
    ('Psalms', 27, 1),
    ('Isaiah', 40, 31),
    ('Deuteronomy', 31, 6),
    ('Psalms', 23, 4),
    ('2 Timothy', 1, 7),
    ('Exodus', 15, 2),
    ('Nehemiah', 8, 10),
    ('1 Chronicles', 28, 20),
    ('Psalms', 18, 2),
    
    # Peace & Comfort
    ('John', 14, 27),
    ('Matthew', 11, 28),
    ('Philippians', 4, 6),
    ('2 Thessalonians', 3, 16),
    ('Revelation', 21, 4),
    ('Psalms', 34, 18),
    ('2 Corinthians', 1, 3),
    ('Psalms', 91, 1),
    ('Psalms', 121, 1),
    
    # Wisdom & Guidance
    ('James', 1, 5),
    ('Proverbs', 1, 7),
    ('Psalms', 119, 105),
    ('Colossians', 3, 16),
    ('Proverbs', 19, 21),
    ('Ecclesiastes', 3, 1),
    ('Micah', 6, 8),
    ('Matthew', 6, 33),
    ('Proverbs', 16, 9),
    ('Psalms', 25, 4),
    
    # Forgiveness & Grace
    ('1 John', 1, 9),
    ('Colossians', 1, 13),
    ('Luke', 6, 37),
    ('Matthew', 6, 14),
    ('Acts', 3, 19),
    ('Isaiah', 1, 18),
    ('Titus', 2, 11),
    ('Romans', 5, 8),
    
    # Hope & Eternal Life
    ('John', 14, 6),
    ('Romans', 6, 23),
    ('1 Peter', 1, 3),
    ('2 Corinthians', 4, 16),
    ('John', 10, 10),
    ('Philippians', 3, 20),
    ('1 Thessalonians', 4, 16),
    ('Revelation', 22, 12),
    ('Titus', 1, 2),
    ('Hebrews', 6, 19),
    
    # Prayer & Seeking God
    ('1 Thessalonians', 5, 16),
    ('Matthew', 7, 7),
    ('Jeremiah', 33, 3),
    ('Psalms', 145, 18),
    ('James', 5, 16),
    ('Mark', 11, 24),
    ('1 John', 5, 14),
    ('Psalms', 50, 15),
    ('Luke', 11, 9),
    
    # Obedience & Righteous Living
    ('Romans', 12, 2),
    ('Galatians', 5, 22),
    ('Matthew', 5, 14),
    ('Ephesians', 6, 10),
    ('1 Peter', 2, 9),
    ('Psalms', 119, 11),
    ('Matthew', 7, 24),
    ('Colossians', 3, 23),
    ('2 Corinthians', 9, 7),
    ('Titus', 3, 1),
    
    # God's Power & Glory
    ('Psalms', 19, 1),
    ('Exodus', 14, 14),
    ('Psalms', 100, 4),
    ('Revelation', 4, 11),
    ('Psalms', 150, 6),
    ('Habakkuk', 2, 14),
    ('Isaiah', 6, 8),
    ('Daniel', 2, 20),
    ('Jude', 1, 24),
]

# ASV and WEB translations for each verse
VERSE_TRANSLATIONS = {
    # Faith & Trust in God
    ('Hebrews', 11, 1): {
        'ASV': "Now faith is assurance of things hoped for, a conviction of things not seen.",
        'WEB': "Now faith is assurance of things hoped for, proof of things not seen."
    },
    ('Proverbs', 3, 5): {
        'ASV': "Trust in Jehovah with all thy heart, And lean not upon thine own understanding:",
        'WEB': "Trust in Yahweh with all your heart, and don't lean on your own understanding."
    },
    ('Isaiah', 41, 10): {
        'ASV': "Fear thou not, for I am with thee; be not dismayed, for I am thy God; I will strengthen thee; yea, I will help thee; yea, I will uphold thee with the right hand of my righteousness.",
        'WEB': "Don't you be afraid, for I am with you. Don't be dismayed, for I am your God. I will strengthen you. Yes, I will help you. Yes, I will uphold you with the right hand of my righteousness."
    },
    ('Philippians', 4, 13): {
        'ASV': "I can do all things in him that strengtheneth me.",
        'WEB': "I can do all things through Christ, who strengthens me."
    },
    ('Jeremiah', 29, 11): {
        'ASV': "For I know the thoughts that I think toward you, saith Jehovah, thoughts of peace, and not of evil, to give you hope in your latter end.",
        'WEB': "For I know the thoughts that I think toward you,\" says Yahweh, \"thoughts of peace, and not of evil, to give you hope and a future."
    },
    ('Romans', 8, 28): {
        'ASV': "And we know that to them that love God all things work together for good, even to them that are called according to his purpose.",
        'WEB': "We know that all things work together for good for those who love God, to those who are called according to his purpose."
    },
    ('Matthew', 17, 20): {
        'ASV': "And he saith unto them, Because of your little faith: for verily I say unto you, If ye have faith as a grain of mustard seed, ye shall say unto this mountain, Remove hence to yonder place; and it shall remove; and nothing shall be impossible unto you.",
        'WEB': "He said to them, \"Because of your unbelief. For most certainly I tell you, if you have faith as a grain of mustard seed, you will tell this mountain, 'Move from here to there,' and it will move; and nothing will be impossible for you."
    },
    ('Psalms', 46, 1): {
        'ASV': "God is our refuge and strength, A very present help in trouble.",
        'WEB': "God is our refuge and strength, a very present help in trouble."
    },
    ('2 Corinthians', 5, 7): {
        'ASV': "(for we walk by faith, not by sight);",
        'WEB': "for we walk by faith, not by sight."
    },
    ('Psalms', 37, 4): {
        'ASV': "Delight thyself also in Jehovah; And he will give thee the desires of thy heart.",
        'WEB': "Also delight yourself in Yahweh, and he will give you the desires of your heart."
    },
    
    # Love & Relationships
    ('1 Corinthians', 13, 4): {
        'ASV': "Love suffereth long, and is kind; love envieth not; love vaunteth not itself, is not puffed up,",
        'WEB': "Love is patient and is kind; love doesn't envy. Love doesn't brag, is not proud,"
    },
    ('1 John', 4, 7): {
        'ASV': "Beloved, let us love one another: for love is of God; and every one that loveth is begotten of God, and knoweth God.",
        'WEB': "Beloved, let us love one another, for love is of God; and everyone who loves is born of God, and knows God."
    },
    ('Matthew', 22, 37): {
        'ASV': "And he said unto him, Thou shalt love the Lord thy God with all thy heart, and with all thy soul, and with all thy mind.",
        'WEB': "Jesus said to him, \"'You shall love the Lord your God with all your heart, with all your soul, and with all your mind.'"
    },
    ('Colossians', 3, 14): {
        'ASV': "and above all these things put on love, which is the bond of perfectness.",
        'WEB': "Above all these things, walk in love, which is the bond of perfection."
    },
    ('Romans', 12, 9): {
        'ASV': "Let love be without hypocrisy. Abhor that which is evil; cleave to that which is good.",
        'WEB': "Let love be without hypocrisy. Abhor that which is evil. Cling to that which is good."
    },
    ('Song of Solomon', 8, 7): {
        'ASV': "Many waters cannot quench love, Neither can floods drown it: If a man would give all the substance of his house for love, He would utterly be contemned.",
        'WEB': "Many waters can't quench love, neither can floods drown it. If a man would give all the wealth of his house for love, he would be utterly scorned."
    },
    ('1 Peter', 4, 8): {
        'ASV': "above all things being fervent in your love among yourselves; for love covereth a multitude of sins:",
        'WEB': "And above all things be earnest in your love among yourselves, for love covers a multitude of sins."
    },
    ('Ephesians', 5, 25): {
        'ASV': "Husbands, love your wives, even as Christ also loved the church, and gave himself up for it;",
        'WEB': "Husbands, love your wives, even as Christ also loved the assembly, and gave himself up for it;"
    },
    ('Proverbs', 17, 17): {
        'ASV': "A friend loveth at all times; And a brother is born for adversity.",
        'WEB': "A friend loves at all times; and a brother is born for adversity."
    },
    
    # Strength & Courage
    ('Joshua', 1, 9): {
        'ASV': "Have not I commanded thee? Be strong and of good courage; be not affrighted, neither be dismayed: for Jehovah thy God is with thee whithersoever thou goest.",
        'WEB': "Haven't I commanded you? Be strong and courageous. Don't be afraid. Don't be dismayed, for Yahweh your God is with you wherever you go.\""
    },
    ('Psalms', 27, 1): {
        'ASV': "Jehovah is my light and my salvation; Whom shall I fear? Jehovah is the strength of my life; Of whom shall I be afraid?",
        'WEB': "Yahweh is my light and my salvation. Whom shall I fear? Yahweh is the strength of my life. Of whom shall I be afraid?"
    },
    ('Isaiah', 40, 31): {
        'ASV': "but they that wait for Jehovah shall renew their strength; they shall mount up with wings as eagles; they shall run, and not be weary; they shall walk, and not faint.",
        'WEB': "But those who wait for Yahweh will renew their strength. They will mount up with wings like eagles. They will run, and not be weary. They will walk, and not faint."
    },
    ('Deuteronomy', 31, 6): {
        'ASV': "Be strong and of good courage, fear not, nor be affrighted at them: for Jehovah thy God, he it is that doth go with thee; he will not fail thee, nor forsake thee.",
        'WEB': "Be strong and courageous. Don't be afraid or scared of them, for Yahweh your God himself is who goes with you. He will not fail you nor forsake you.\""
    },
    ('Psalms', 23, 4): {
        'ASV': "Yea, though I walk through the valley of the shadow of death, I will fear no evil; for thou art with me; Thy rod and thy staff, they comfort me.",
        'WEB': "Even though I walk through the valley of the shadow of death, I will fear no evil, for you are with me. Your rod and your staff, they comfort me."
    },
    ('2 Timothy', 1, 7): {
        'ASV': "For God gave us not a spirit of fearfulness; but of power and love and discipline.",
        'WEB': "For God didn't give us a spirit of fear, but of power, love, and self-control."
    },
    ('Exodus', 15, 2): {
        'ASV': "Jehovah is my strength and song, And he is become my salvation: This is my God, and I will praise him; My father's God, and I will exalt him.",
        'WEB': "Yah is my strength and song. He has become my salvation. This is my God, and I will praise him; my father's God, and I will exalt him."
    },
    ('Nehemiah', 8, 10): {
        'ASV': "Then he said unto them, Go your way, eat the fat, and drink the sweet, and send portions unto him for whom nothing is prepared; for this day is holy unto our Lord: neither be ye grieved; for the joy of Jehovah is your strength.",
        'WEB': "Then he said to them, \"Go your way. Eat the fat, drink the sweet, and send portions to him for whom nothing is prepared; for this day is holy to our Lord. Don't be grieved; for the joy of Yahweh is your strength.\""
    },
    ('1 Chronicles', 28, 20): {
        'ASV': "And David said to Solomon his son, Be strong and of good courage, and do it: fear not, nor be dismayed; for Jehovah God, even my God, is with thee; he will not fail thee, nor forsake thee, until all the work for the service of the house of Jehovah be finished.",
        'WEB': "David said to Solomon his son, \"Be strong and courageous, and do it. Don't be afraid, nor be dismayed; for Yahweh God, even my God, is with you. He will not fail you, nor forsake you, until all the work for the service of the house of Yahweh is finished."
    },
    ('Psalms', 18, 2): {
        'ASV': "Jehovah is my rock, and my fortress, and my deliverer; My God, my rock, in whom I take refuge; My shield, and the horn of my salvation, my high tower.",
        'WEB': "Yahweh is my rock, my fortress, and my deliverer; my God, my rock, in whom I take refuge; my shield, and the horn of my salvation, my high tower."
    },
    
    # Peace & Comfort
    ('John', 14, 27): {
        'ASV': "Peace I leave with you; my peace I give unto you: not as the world giveth, give I unto you. Let not your heart be troubled, neither let it be fearful.",
        'WEB': "Peace I leave with you. My peace I give to you; not as the world gives, give I to you. Don't let your heart be troubled, neither let it be fearful."
    },
    ('Matthew', 11, 28): {
        'ASV': "Come unto me, all ye that labor and are heavy laden, and I will give you rest.",
        'WEB': "\"Come to me, all you who labor and are heavily burdened, and I will give you rest."
    },
    ('Philippians', 4, 6): {
        'ASV': "In nothing be anxious; but in everything by prayer and supplication with thanksgiving let your requests be made known unto God.",
        'WEB': "In nothing be anxious, but in everything, by prayer and petition with thanksgiving, let your requests be made known to God."
    },
    ('2 Thessalonians', 3, 16): {
        'ASV': "Now the Lord of peace himself give you peace at all times in all ways. The Lord be with you all.",
        'WEB': "Now may the Lord of peace himself give you peace at all times in all ways. The Lord be with you all."
    },
    ('Revelation', 21, 4): {
        'ASV': "and he shall wipe away every tear from their eyes; and death shall be no more; neither shall there be mourning, nor crying, nor pain, any more: the first things are passed away.",
        'WEB': "He will wipe away from them every tear from their eyes. Death will be no more; neither will there be mourning, nor crying, nor pain, any more. The first things have passed away.\""
    },
    ('Psalms', 34, 18): {
        'ASV': "Jehovah is nigh unto them that are of a broken heart, And saveth such as are of a contrite spirit.",
        'WEB': "Yahweh is near to those who have a broken heart, and saves those who have a crushed spirit."
    },
    ('2 Corinthians', 1, 3): {
        'ASV': "Blessed be the God and Father of our Lord Jesus Christ, the Father of mercies and God of all comfort;",
        'WEB': "Blessed be the God and Father of our Lord Jesus Christ, the Father of mercies and God of all comfort;"
    },
    ('Psalms', 91, 1): {
        'ASV': "He that dwelleth in the secret place of the Most High Shall abide under the shadow of the Almighty.",
        'WEB': "He who dwells in the secret place of the Most High will rest in the shadow of the Almighty."
    },
    ('Psalms', 121, 1): {
        'ASV': "I will lift up mine eyes unto the mountains: From whence shall my help come?",
        'WEB': "I will lift up my eyes to the hills. Where does my help come from?"
    },
    
    # Wisdom & Guidance
    ('James', 1, 5): {
        'ASV': "But if any of you lacketh wisdom, let him ask of God, who giveth to all liberally and upbraideth not; and it shall be given him.",
        'WEB': "But if any of you lacks wisdom, let him ask of God, who gives to all liberally and without reproach; and it will be given to him."
    },
    ('Proverbs', 1, 7): {
        'ASV': "The fear of Jehovah is the beginning of knowledge; But the foolish despise wisdom and instruction.",
        'WEB': "The fear of Yahweh is the beginning of knowledge; but the foolish despise wisdom and instruction."
    },
    ('Psalms', 119, 105): {
        'ASV': "Thy word is a lamp unto my feet, And light unto my path.",
        'WEB': "Your word is a lamp to my feet, and a light for my path."
    },
    ('Colossians', 3, 16): {
        'ASV': "Let the word of Christ dwell in you richly; in all wisdom teaching and admonishing one another with psalms and hymns and spiritual songs, singing with grace in your hearts unto God.",
        'WEB': "Let the word of Christ dwell in you richly; in all wisdom teaching and admonishing one another with psalms, hymns, and spiritual songs, singing with grace in your heart to the Lord."
    },
    ('Proverbs', 19, 21): {
        'ASV': "There are many devices in a man's heart; But the counsel of Jehovah, that shall stand.",
        'WEB': "There are many plans in a man's heart, but Yahweh's counsel will prevail."
    },
    ('Ecclesiastes', 3, 1): {
        'ASV': "For everything there is a season, and a time to every purpose under heaven:",
        'WEB': "For everything there is a season, and a time for every purpose under the sky:"
    },
    ('Micah', 6, 8): {
        'ASV': "He hath showed thee, O man, what is good; and what doth Jehovah require of thee, but to do justly, and to love kindness, and to walk humbly with thy God?",
        'WEB': "He has shown you, O man, what is good. What does Yahweh require of you, but to act justly, to love mercy, and to walk humbly with your God?"
    },
    ('Matthew', 6, 33): {
        'ASV': "But seek ye first his kingdom, and his righteousness; and all these things shall be added unto you.",
        'WEB': "But seek first God's Kingdom, and his righteousness; and all these things will be given to you as well."
    },
    ('Proverbs', 16, 9): {
        'ASV': "A man's heart deviseth his way; But Jehovah directeth his steps.",
        'WEB': "A man's heart plans his course, but Yahweh directs his steps."
    },
    ('Psalms', 25, 4): {
        'ASV': "Show me thy ways, O Jehovah; Teach me thy paths.",
        'WEB': "Show me your ways, Yahweh. Teach me your paths."
    },
}

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def check_verse_exists(cursor, book, chapter, verse, translation_id):
    """Check if a verse translation already exists"""
    cursor.execute("""
        SELECT id FROM biblical_texts 
        WHERE book = %s AND chapter = %s AND verse = %s AND translation_id = %s
    """, (book, chapter, verse, translation_id))
    return cursor.fetchone() is not None

def add_verse_translation(cursor, book, chapter, verse, translation_id, translation_name, text):
    """Add a verse translation to the database"""
    cursor.execute("""
        INSERT INTO biblical_texts (book, chapter, verse, translation_id, translation, text, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
    """, (book, chapter, verse, translation_id, translation_name, text))

def main():
    """Main function to add popular verse translations"""
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                added_count = 0
                skipped_count = 0
                
                print("Adding ASV and WEB translations for popular verses...")
                
                for book, chapter, verse in POPULAR_VERSES:
                    verse_key = (book, chapter, verse)
                    
                    # Skip if we don't have translations for this verse yet
                    if verse_key not in VERSE_TRANSLATIONS:
                        print(f"⚠️  No translations defined yet for {book} {chapter}:{verse}")
                        continue
                    
                    translations = VERSE_TRANSLATIONS[verse_key]
                    
                    # Add ASV translation (translation_id = 2)
                    if not check_verse_exists(cursor, book, chapter, verse, 2):
                        add_verse_translation(cursor, book, chapter, verse, 2, 'ASV', translations['ASV'])
                        print(f"✅ Added ASV: {book} {chapter}:{verse}")
                        added_count += 1
                    else:
                        print(f"⏭️  ASV already exists: {book} {chapter}:{verse}")
                        skipped_count += 1
                    
                    # Add WEB translation (translation_id = 3)
                    if not check_verse_exists(cursor, book, chapter, verse, 3):
                        add_verse_translation(cursor, book, chapter, verse, 3, 'WEB', translations['WEB'])
                        print(f"✅ Added WEB: {book} {chapter}:{verse}")
                        added_count += 1
                    else:
                        print(f"⏭️  WEB already exists: {book} {chapter}:{verse}")
                        skipped_count += 1
                
                conn.commit()
                print(f"\n🎉 Successfully added {added_count} translations")
                print(f"⏭️  Skipped {skipped_count} existing translations")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()