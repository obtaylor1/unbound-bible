#!/usr/bin/env python3
"""
Copyright Enforcement Logic

Implements copyright protection for restricted biblical texts and editions.
Prevents unauthorized distribution of commercial products like BHS/NA28
while providing proper attribution and purchasing information.
"""

import sys
import os
from typing import Dict, Optional, Union, Any
from enum import Enum

# Add backend and server paths for imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_path)
sys.path.insert(0, os.path.join(server_path, 'models'))

from sqlalchemy.orm import Session

try:
    # Import from backend
    from database import get_db
    from models import BiblicalText, Translation
    # Import from server models
    from edition_metadata import EditionMetadata, IngestStatusEnum
    from dss_reference import DssReference
except ImportError as e:
    print(f"Import error in copyright_enforcement: {e}")
    # Try alternative import path
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from dss_reference import DssReference
    except ImportError as e2:
        print(f"Alternative import failed: {e2}")
        raise e


class LicenseType(Enum):
    """Enumeration of license types for copyright enforcement"""
    PUBLIC_DOMAIN = "PD"
    CREATIVE_COMMONS_BY = "CC BY"
    CREATIVE_COMMONS_BY_SA = "CC BY-SA"
    CREATIVE_COMMONS_BY_NC = "CC BY-NC"
    ALL_RIGHTS_RESERVED = "ARR"
    COMMERCIAL = "COMMERCIAL"
    RESTRICTED = "RESTRICTED"


class CopyrightError(Exception):
    """Exception raised when attempting to access copyrighted content"""
    pass


class CopyrightEnforcer:
    """Handles copyright enforcement for biblical texts and editions"""
    
    def __init__(self, db_session: Optional[Session] = None):
        self.session = db_session or next(get_db())
        
        # Define which licenses allow full text access
        self.public_licenses = {
            LicenseType.PUBLIC_DOMAIN.value,
            LicenseType.CREATIVE_COMMONS_BY.value,
            LicenseType.CREATIVE_COMMONS_BY_SA.value,
            LicenseType.CREATIVE_COMMONS_BY_NC.value
        }
        
        # Define restricted licenses that require payment/subscription
        self.restricted_licenses = {
            LicenseType.ALL_RIGHTS_RESERVED.value,
            LicenseType.COMMERCIAL.value,
            LicenseType.RESTRICTED.value
        }

    def get_text_by_edition(self, edition_id: str, book: str = None, chapter: int = None, verse: int = None) -> Dict[str, Any]:
        """
        Retrieve text by edition with copyright enforcement.
        
        Args:
            edition_id: The work_id from EditionMetadata
            book: Optional book name filter
            chapter: Optional chapter filter  
            verse: Optional verse filter
            
        Returns:
            Dictionary containing either the text data or copyright restriction info
            
        Raises:
            CopyrightError: If attempting to access restricted content
        """
        
        # Get edition metadata
        edition = self.session.query(EditionMetadata).filter(
            EditionMetadata.work_id == edition_id
        ).first()
        
        if not edition:
            return {
                "error": "Edition not found",
                "edition_id": edition_id,
                "requires_licensing": False
            }
        
        # Check license restrictions
        license_type = edition.license
        requires_licensing = license_type in self.restricted_licenses
        
        # If restricted license, return copyright information instead of text
        if requires_licensing:
            return {
                "error": f"This edition ({edition.source_title}) is protected by copyright ({license_type})",
                "message": "Full text access requires proper licensing or subscription",
                "edition_id": edition_id,
                "source_title": edition.source_title,
                "editor_translator": edition.editor_translator,
                "publisher": edition.publisher,
                "license": license_type,
                "provenance_url": edition.provenance_url,
                "requires_licensing": True,
                "access_instructions": self._get_access_instructions(license_type, edition.provenance_url)
            }
        
        # For public domain content, retrieve and return the text
        try:
            query = self.session.query(BiblicalText).join(Translation).filter(
                Translation.code.in_(self._get_translation_codes_for_edition(edition_id))
            )
            
            # Apply optional filters
            if book:
                query = query.filter(BiblicalText.book == book)
            if chapter:
                query = query.filter(BiblicalText.chapter == chapter)
            if verse:
                query = query.filter(BiblicalText.verse == verse)
            
            texts = query.all()
            
            if not texts:
                return {
                    "error": "No text found for specified criteria",
                    "edition_id": edition_id,
                    "requires_licensing": False
                }
            
            # Format response with public domain texts
            return {
                "success": True,
                "edition_id": edition_id,
                "source_title": edition.source_title,
                "license": license_type,
                "requires_licensing": False,
                "texts": [
                    {
                        "book": text.book,
                        "chapter": text.chapter,
                        "verse": text.verse,
                        "text": text.text,
                        "translation": text.translation
                    }
                    for text in texts
                ]
            }
            
        except Exception as e:
            return {
                "error": f"Database error: {str(e)}",
                "edition_id": edition_id,
                "requires_licensing": requires_licensing
            }

    def _get_translation_codes_for_edition(self, edition_id: str) -> list:
        """Get translation codes associated with an edition"""
        
        # Map edition IDs to translation codes
        edition_translation_map = {
            "KJV_COMPLETE": ["KJV"],
            "WEBBE_COMPLETE": ["WEBBE"],
            "1_ENOCH_CHARLES": ["1EN_CH"],
            "JUBILEES_CHARLES": ["JUB_CH"],
            "MEQABYAN_1_WIKISOURCE": ["MEQ1"],
            "JOSEPHUS_WHISTON": ["JOSEPHUS"],
            "TARGUM_ONKELOS_PD": ["TARG_ON"],
            "BHS_CRITICAL": ["BHS"],
            "NA28_CRITICAL": ["NA28"]
        }
        
        return edition_translation_map.get(edition_id, [])

    def _get_access_instructions(self, license_type: str, provenance_url: str) -> str:
        """Generate instructions for accessing restricted content"""
        
        instructions = {
            LicenseType.ALL_RIGHTS_RESERVED.value: 
                "This text is under copyright protection. Please purchase or subscribe through the official publisher.",
            LicenseType.COMMERCIAL.value:
                "This is a commercial product. Please obtain a valid license from the publisher.",
            LicenseType.RESTRICTED.value:
                "Access to this text requires institutional subscription or individual licensing."
        }
        
        base_instruction = instructions.get(license_type, "This content requires proper licensing.")
        
        if provenance_url:
            return f"{base_instruction} Access available at: {provenance_url}"
        else:
            return base_instruction

    def check_license_requirements(self, edition_id: str) -> Dict[str, Any]:
        """
        Check licensing requirements for an edition without accessing text.
        
        Args:
            edition_id: The work_id from EditionMetadata
            
        Returns:
            Dictionary with licensing information
        """
        
        edition = self.session.query(EditionMetadata).filter(
            EditionMetadata.work_id == edition_id
        ).first()
        
        if not edition:
            return {
                "found": False,
                "edition_id": edition_id,
                "requires_licensing": False
            }
        
        requires_licensing = edition.license in self.restricted_licenses
        
        return {
            "found": True,
            "edition_id": edition_id,
            "source_title": edition.source_title,
            "license": edition.license,
            "requires_licensing": requires_licensing,
            "is_public_domain": edition.license in self.public_licenses,
            "provenance_url": edition.provenance_url
        }

    def add_licensing_flag_to_response(self, response_data: Dict[str, Any], edition_id: str) -> Dict[str, Any]:
        """
        Add requires_licensing_flag to API response data.
        
        Args:
            response_data: Original API response dictionary
            edition_id: Edition identifier to check
            
        Returns:
            Modified response with licensing flag
        """
        
        license_info = self.check_license_requirements(edition_id)
        
        response_data["requires_licensing_flag"] = license_info.get("requires_licensing", False)
        response_data["license_type"] = license_info.get("license", "UNKNOWN")
        
        if license_info.get("requires_licensing"):
            response_data["access_url"] = license_info.get("provenance_url")
            response_data["license_message"] = "Full text requires proper licensing"
        
        return response_data

    def get_dss_reference(self, fragment_id: str) -> Dict[str, Any]:
        """
        Get Dead Sea Scrolls reference metadata.
        
        Args:
            fragment_id: DSS fragment identifier (e.g., "1QIsa")
            
        Returns:
            Dictionary with DSS reference information or error
        """
        
        dss_ref = self.session.query(DssReference).filter(
            DssReference.fragment_id == fragment_id
        ).first()
        
        if not dss_ref:
            return {
                "error": "DSS fragment not found",
                "fragment_id": fragment_id
            }
        
        return {
            "success": True,
            "fragment_id": dss_ref.fragment_id,
            "scripture_ref": dss_ref.scripture_ref,
            "iaa_url": dss_ref.iaa_url,
            "cave_number": dss_ref.cave_number,
            "scroll_name": dss_ref.scroll_name,
            "description": dss_ref.description,
            "access_note": "Full manuscript images available through Israel Antiquities Authority"
        }

    def create_sample_restricted_editions(self):
        """Create sample restricted edition metadata for testing"""
        
        # Check if BHS already exists
        existing_bhs = self.session.query(EditionMetadata).filter(
            EditionMetadata.work_id == "BHS_CRITICAL"
        ).first()
        
        if not existing_bhs:
            bhs_edition = EditionMetadata(
                work_id="BHS_CRITICAL",
                language_script="hbo/Hebrew",
                canon_tags=["protestant", "critical"],
                source_title="Biblia Hebraica Stuttgartensia (BHS)",
                editor_translator="K. Elliger, W. Rudolph et al.",
                publisher="Deutsche Bibelgesellschaft",
                license="ARR",
                provenance_url="https://www.bibelgesellschaft.de/en/bible-texts/scientific-editions/",
                has_morph=True,
                ingest_status=IngestStatusEnum.queued
            )
            self.session.add(bhs_edition)
        
        # Check if NA28 already exists
        existing_na28 = self.session.query(EditionMetadata).filter(
            EditionMetadata.work_id == "NA28_CRITICAL"
        ).first()
        
        if not existing_na28:
            na28_edition = EditionMetadata(
                work_id="NA28_CRITICAL",
                language_script="grc/Greek",
                canon_tags=["protestant", "critical"],
                source_title="Novum Testamentum Graece (Nestle-Aland 28th Edition)",
                editor_translator="Nestle-Aland Editorial Committee",
                publisher="Deutsche Bibelgesellschaft",
                license="ARR",
                provenance_url="https://www.nestle-aland.com/en/",
                has_morph=True,
                ingest_status=IngestStatusEnum.queued
            )
            self.session.add(na28_edition)
        
        self.session.commit()
        print("✓ Created sample restricted edition metadata (BHS, NA28)")

    def create_sample_dss_references(self):
        """Create sample DSS reference records"""
        
        sample_dss_refs = [
            {
                "fragment_id": "1QIsa",
                "scripture_ref": "Isaiah (Complete)",
                "iaa_url": "https://www.deadseascrolls.org.il/explore-the-archive/manuscript/4Q161-1",
                "cave_number": "1",
                "scroll_name": "Great Isaiah Scroll",
                "description": "Complete scroll of Isaiah, one of the most famous Dead Sea Scrolls"
            },
            {
                "fragment_id": "4Q175",
                "scripture_ref": "Deuteronomy 5:28-29, 18:18-19",
                "iaa_url": "https://www.deadseascrolls.org.il/explore-the-archive/manuscript/4Q175-1",
                "cave_number": "4",
                "scroll_name": "Testimonia",
                "description": "Collection of messianic prophecies"
            },
            {
                "fragment_id": "11QPsa",
                "scripture_ref": "Psalms (Partial)",
                "iaa_url": "https://www.deadseascrolls.org.il/explore-the-archive/manuscript/11Q5-1",
                "cave_number": "11",
                "scroll_name": "Psalms Scroll",
                "description": "Large Psalms scroll with canonical and non-canonical psalms"
            }
        ]
        
        for ref_data in sample_dss_refs:
            # Check if already exists
            existing = self.session.query(DssReference).filter(
                DssReference.fragment_id == ref_data["fragment_id"]
            ).first()
            
            if not existing:
                dss_ref = DssReference(**ref_data)
                self.session.add(dss_ref)
        
        self.session.commit()
        print("✓ Created sample DSS reference records")


def demonstrate_copyright_enforcement():
    """Demonstration of copyright enforcement functionality"""
    
    print("=== Copyright Enforcement System Demonstration ===")
    print()
    
    enforcer = CopyrightEnforcer()
    
    # Create sample restricted editions and DSS references
    print("Creating sample data...")
    enforcer.create_sample_restricted_editions()
    enforcer.create_sample_dss_references()
    print()
    
    # Test public domain access
    print("Testing public domain access (KJV):")
    kjv_result = enforcer.get_text_by_edition("KJV_COMPLETE", "Genesis", 1, 1)
    if kjv_result.get("success"):
        print("✓ KJV access granted (public domain)")
        print(f"  License: {kjv_result['license']}")
        print(f"  Requires licensing: {kjv_result['requires_licensing']}")
    else:
        print(f"  Error: {kjv_result.get('error')}")
    print()
    
    # Test restricted access
    print("Testing restricted access (BHS):")
    bhs_result = enforcer.get_text_by_edition("BHS_CRITICAL", "Genesis", 1, 1)
    if bhs_result.get("error"):
        print("✓ BHS access properly restricted")
        print(f"  License: {bhs_result['license']}")
        print(f"  Requires licensing: {bhs_result['requires_licensing']}")
        print(f"  Access URL: {bhs_result['provenance_url']}")
        print(f"  Instructions: {bhs_result['access_instructions']}")
    else:
        print("❌ BHS access should be restricted!")
    print()
    
    # Test DSS reference
    print("Testing DSS reference access:")
    dss_result = enforcer.get_dss_reference("1QIsa")
    if dss_result.get("success"):
        print("✓ DSS reference retrieved successfully")
        print(f"  Fragment: {dss_result['fragment_id']}")
        print(f"  Scripture: {dss_result['scripture_ref']}")
        print(f"  IAA URL: {dss_result['iaa_url']}")
        print(f"  Description: {dss_result['description']}")
    else:
        print(f"  Error: {dss_result.get('error')}")
    print()
    
    # Test licensing flag functionality
    print("Testing API response licensing flags:")
    sample_response = {"text": "Sample biblical text", "book": "Genesis"}
    
    # Add licensing flag for public domain
    kjv_flagged = enforcer.add_licensing_flag_to_response(sample_response.copy(), "KJV_COMPLETE")
    print(f"KJV response requires_licensing_flag: {kjv_flagged['requires_licensing_flag']}")
    
    # Add licensing flag for restricted content
    bhs_flagged = enforcer.add_licensing_flag_to_response(sample_response.copy(), "BHS_CRITICAL")
    print(f"BHS response requires_licensing_flag: {bhs_flagged['requires_licensing_flag']}")
    
    print()
    print("✅ Copyright enforcement system operational!")
    print("Key features:")
    print("  - License checking prevents ARR text access")
    print("  - DSS metadata-only storage respects IAA rights")
    print("  - UI licensing flags guide frontend behavior")
    print("  - Proper attribution and access URLs provided")


if __name__ == "__main__":
    demonstrate_copyright_enforcement()