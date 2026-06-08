#!/usr/bin/env python3
"""
Biblical Geography Data Ingestion Script
Downloads and imports biblical geographical data from OpenBible.info into the database.
"""

import requests
import csv
import json
import logging
from io import StringIO
from sqlalchemy.orm import Session
from database import engine, get_db
from models import Base, GeographicalLocation, BiblicalText
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenBible.info geographical data sources (Updated URLs from GitHub repository)
OPENBIBLE_DATA_URLS = {
    # JSONL format data files from the official GitHub repository
    'ancient': 'https://raw.githubusercontent.com/openbibleinfo/Bible-Geocoding-Data/main/data/ancient.jsonl',
    'modern': 'https://raw.githubusercontent.com/openbibleinfo/Bible-Geocoding-Data/main/data/modern.jsonl'
}

def download_geographical_data():
    """Download biblical geographical data from OpenBible.info GitHub repository"""
    logger.info("Downloading biblical geographical data from OpenBible.info...")
    
    all_locations = []
    
    try:
        # Download ancient biblical locations (JSONL format)
        logger.info("Downloading ancient geographical data...")
        ancient_response = requests.get(OPENBIBLE_DATA_URLS['ancient'])
        ancient_response.raise_for_status()
        
        # Parse JSONL data (one JSON object per line)
        ancient_locations = []
        for line in ancient_response.text.strip().split('\n'):
            if line.strip():
                try:
                    location_data = json.loads(line)
                    ancient_locations.append(location_data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Skipping malformed JSON line: {e}")
                    continue
        
        logger.info(f"Downloaded {len(ancient_locations)} ancient location entries")
        all_locations.extend(ancient_locations)
        
        # Download modern geographical associations (JSONL format)
        logger.info("Downloading modern geographical data...")
        modern_response = requests.get(OPENBIBLE_DATA_URLS['modern'])
        modern_response.raise_for_status()
        
        # Parse modern JSONL data
        modern_locations = []
        for line in modern_response.text.strip().split('\n'):
            if line.strip():
                try:
                    location_data = json.loads(line)
                    modern_locations.append(location_data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Skipping malformed modern JSON line: {e}")
                    continue
        
        logger.info(f"Downloaded {len(modern_locations)} modern location entries")
        all_locations.extend(modern_locations)
        
        logger.info(f"Total downloaded entries: {len(all_locations)}")
        return all_locations
        
    except requests.RequestException as e:
        logger.error(f"Failed to download geographical data: {e}")
        # Fallback to sample data structure
        return create_sample_geographical_data()

def create_sample_geographical_data():
    """Create sample geographical data for key biblical locations"""
    logger.info("Creating sample geographical data for key biblical locations...")
    
    sample_data = [
        {
            'Name': 'Jerusalem',
            'Latitude': '31.7690',
            'Longitude': '35.2163',
            'Description': 'Holy city, capital of ancient Israel and modern Israel',
            'Modern_Name': 'Jerusalem, Israel',
            'Verses': 'Many references throughout the Bible'
        },
        {
            'Name': 'Bethlehem',
            'Latitude': '31.7054',
            'Longitude': '35.2024', 
            'Description': 'Birthplace of Jesus Christ and King David',
            'Modern_Name': 'Bethlehem, Palestine',
            'Verses': 'Matthew 2:1, Luke 2:4-15, Micah 5:2'
        },
        {
            'Name': 'Nazareth',
            'Latitude': '32.7029',
            'Longitude': '35.2968',
            'Description': 'Hometown of Jesus Christ',
            'Modern_Name': 'Nazareth, Israel',
            'Verses': 'Matthew 2:23, Luke 1:26, Luke 4:16'
        },
        {
            'Name': 'Sea of Galilee',
            'Latitude': '32.8333',
            'Longitude': '35.5833',
            'Description': 'Freshwater lake where Jesus performed many miracles',
            'Modern_Name': 'Sea of Galilee (Kinneret), Israel',
            'Verses': 'Matthew 4:18, Mark 1:16, John 6:1'
        },
        {
            'Name': 'Mount Sinai',
            'Latitude': '28.5391',
            'Longitude': '33.9734',
            'Description': 'Mountain where Moses received the Ten Commandments',
            'Modern_Name': 'Jebel Musa, Egypt',
            'Verses': 'Exodus 19:18, Exodus 24:16, Deuteronomy 4:10'
        },
        {
            'Name': 'River Jordan',
            'Latitude': '32.0000',
            'Longitude': '35.5000',
            'Description': 'River where Jesus was baptized',
            'Modern_Name': 'Jordan River',
            'Verses': 'Matthew 3:13, Mark 1:9, Joshua 3:17'
        },
        {
            'Name': 'Mount of Olives',
            'Latitude': '31.7784',
            'Longitude': '35.2412',
            'Description': 'Mountain overlooking Jerusalem, site of Jesus ascension',
            'Modern_Name': 'Mount of Olives, Jerusalem',
            'Verses': 'Matthew 21:1, Acts 1:9-12, Zechariah 14:4'
        },
        {
            'Name': 'Capernaum',
            'Latitude': '32.8795',
            'Longitude': '35.5753',
            'Description': 'Town on Sea of Galilee, base of Jesus ministry',
            'Modern_Name': 'Kfar Nahum, Israel',
            'Verses': 'Matthew 4:13, Mark 2:1, Luke 4:31'
        },
        {
            'Name': 'Jericho',
            'Latitude': '31.8700',
            'Longitude': '35.4441',
            'Description': 'Ancient city conquered by Joshua',
            'Modern_Name': 'Jericho, Palestine',
            'Verses': 'Joshua 6:1-27, Luke 18:35, Luke 19:1'
        },
        {
            'Name': 'Damascus',
            'Latitude': '33.5138',
            'Longitude': '36.2765',
            'Description': 'Ancient city where Paul was converted',
            'Modern_Name': 'Damascus, Syria',
            'Verses': 'Acts 9:1-22, 2 Corinthians 11:32'
        },
        {
            'Name': 'Babylon',
            'Latitude': '32.5355',
            'Longitude': '44.4275',
            'Description': 'Ancient empire where Israelites were exiled',
            'Modern_Name': 'Near Hillah, Iraq',
            'Verses': 'Daniel 1:1, Jeremiah 29:1, Revelation 14:8'
        },
        {
            'Name': 'Egypt',
            'Latitude': '26.8206',
            'Longitude': '30.8025',
            'Description': 'Land of bondage for the Israelites',
            'Modern_Name': 'Egypt',
            'Verses': 'Exodus 1:8-14, Matthew 2:13-15'
        }
    ]
    
    return sample_data

def standardize_geographical_data(raw_data):
    """Standardize the geographical data format from JSONL to consistent format"""
    logger.info("Standardizing geographical data...")
    
    standardized_data = []
    
    for place in raw_data:
        # Handle different data structures
        name = ""
        latitude = ""
        longitude = ""
        description = ""
        modern_name = ""
        
        try:
            # For ancient biblical locations (from ancient.jsonl)
            if 'friendly_id' in place:
                name = place.get('friendly_id', '')
                
                # Extract coordinates from identifications or lonlat
                identifications = place.get('identifications', [])
                if identifications and isinstance(identifications, list):
                    for identification in identifications:
                        resolutions = identification.get('resolutions', [])
                        if resolutions and isinstance(resolutions, list):
                            resolution = resolutions[0]  # Use first resolution
                            lonlat = resolution.get('lonlat', '')
                            if lonlat and ',' in lonlat:
                                try:
                                    lon_str, lat_str = lonlat.split(',', 1)
                                    longitude = lon_str.strip()
                                    latitude = lat_str.strip()
                                    break
                                except ValueError:
                                    continue
                
                # Build description from various sources
                desc_parts = []
                if identifications:
                    for identification in identifications:
                        if 'description' in identification:
                            desc_parts.append(identification['description'])
                            
                description = ' | '.join(desc_parts) if desc_parts else place.get('url_slug', '')
                
                # Extract modern name from identifications
                modern_parts = []
                for identification in identifications:
                    resolutions = identification.get('resolutions', [])
                    for resolution in resolutions:
                        if 'description' in resolution:
                            modern_parts.append(resolution['description'])
                modern_name = ' | '.join(modern_parts) if modern_parts else ''
            
            # For modern locations (from modern.jsonl)
            elif 'friendly_id' in place and 'lonlat' in place:
                name = place.get('friendly_id', '')
                lonlat = place.get('lonlat', '')
                if lonlat and ',' in lonlat:
                    try:
                        lon_str, lat_str = lonlat.split(',', 1)
                        longitude = lon_str.strip()
                        latitude = lat_str.strip()
                    except ValueError:
                        continue
                
                # Extract description and modern name
                names = place.get('names', [])
                if names and isinstance(names, list):
                    modern_name = names[0].get('name', '') if names else ''
                
                description = f"{place.get('type', '')} - {place.get('class', '')}" if place.get('type') else ''
            
            # Handle legacy sample data format
            elif 'Name' in place or 'name' in place:
                name = place.get('Name') or place.get('name', '')
                latitude = place.get('Latitude') or place.get('latitude', '')
                longitude = place.get('Longitude') or place.get('longitude', '')
                description = place.get('Description') or place.get('description', '')
                modern_name = place.get('Modern_Name') or place.get('modern_name', '')
            
            # Clean and validate coordinates
            if latitude and longitude and name:
                try:
                    lat_float = float(latitude)
                    lon_float = float(longitude)
                    
                    # Basic validation for reasonable coordinates
                    if -90 <= lat_float <= 90 and -180 <= lon_float <= 180:
                        # Clean HTML tags from descriptions
                        description = re.sub(r'<[^>]+>', '', description)
                        modern_name = re.sub(r'<[^>]+>', '', modern_name)
                        
                        standardized_data.append({
                            'name': name.strip(),
                            'latitude': str(lat_float),
                            'longitude': str(lon_float),
                            'description': description.strip()[:500],  # Limit description length
                            'modern_name': modern_name.strip()[:200] if modern_name else ''  # Limit modern name length
                        })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping location '{name}' due to invalid coordinates: {e}")
                    continue
            else:
                logger.warning(f"Skipping location due to missing data: name={name}, lat={latitude}, lon={longitude}")
                        
        except Exception as e:
            logger.warning(f"Error processing location data: {e}")
            continue
    
    logger.info(f"Standardized {len(standardized_data)} geographical entries")
    return standardized_data

def import_geographical_data_to_db(geographical_data, db: Session):
    """Import geographical data into the database"""
    logger.info("Importing geographical data to database...")
    
    # Clear existing geographical locations
    db.query(GeographicalLocation).delete()
    db.commit()
    
    batch_size = 100
    imported_count = 0
    
    for i in range(0, len(geographical_data), batch_size):
        batch = geographical_data[i:i + batch_size]
        db_locations = []
        
        for location_data in batch:
            db_location = GeographicalLocation(
                name=location_data['name'],
                modern_name=location_data['modern_name'],
                latitude=location_data['latitude'],
                longitude=location_data['longitude'],
                description=location_data['description']
                # Note: biblical_text_id is left null for now - will be linked later
            )
            db_locations.append(db_location)
            
        db.add_all(db_locations)
        db.commit()
        imported_count += len(db_locations)
        
        logger.info(f"Imported {imported_count}/{len(geographical_data)} geographical locations")
    
    logger.info(f"Successfully imported {imported_count} geographical locations")

def create_additional_biblical_locations():
    """Create additional important biblical locations"""
    additional_locations = [
        {
            'name': 'Garden of Eden',
            'latitude': '33.0000',  # Approximate - traditional location
            'longitude': '44.0000',
            'description': 'Paradise where Adam and Eve lived before the fall',
            'modern_name': 'Traditional location: Mesopotamia region'
        },
        {
            'name': 'Mount Ararat',
            'latitude': '39.7016',
            'longitude': '44.2978',
            'description': 'Mountain where Noah\'s ark came to rest',
            'modern_name': 'Ararat Mountains, Turkey'
        },
        {
            'name': 'Sodom',
            'latitude': '31.2000',
            'longitude': '35.4000',
            'description': 'Ancient city destroyed for wickedness',
            'modern_name': 'Possible location: Dead Sea region'
        },
        {
            'name': 'Gomorrah',
            'latitude': '31.2000',
            'longitude': '35.4500',
            'description': 'Ancient city destroyed with Sodom',
            'modern_name': 'Possible location: Dead Sea region'
        },
        {
            'name': 'Calvary',
            'latitude': '31.7784',
            'longitude': '35.2295',
            'description': 'Hill where Jesus was crucified',
            'modern_name': 'Church of the Holy Sepulchre area, Jerusalem'
        }
    ]
    
    return additional_locations

def main():
    """Main geographical data ingestion function"""
    logger.info("Starting biblical geographical data ingestion...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    
    # Get database session
    db = next(get_db())
    
    try:
        # Download geographical data
        raw_data = download_geographical_data()
        
        # Add additional biblical locations
        additional_data = create_additional_biblical_locations()
        all_data = raw_data + additional_data
        
        # Standardize the data
        standardized_data = standardize_geographical_data(all_data)
        
        # Import to database
        import_geographical_data_to_db(standardized_data, db)
        
        logger.info("Biblical geographical data ingestion completed successfully!")
        
        # Print statistics
        total_locations = db.query(GeographicalLocation).count()
        logger.info(f"Total geographical locations in database: {total_locations}")
        
    except Exception as e:
        logger.error(f"Error during geographical data ingestion: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()