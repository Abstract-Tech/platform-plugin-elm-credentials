"""Builds ELM credentials."""
from uuid import uuid4

from django.conf import settings

from platform_plugin_elm_credentials.api.serializers import (
    Address,
    AwardedBy,
    AwardingBody,
    CountryCode,
    CredentialSubject,
    CreditPoint,
    DeliveryDetails,
    DisplayParameter,
    Grade,
    HasClaim,
    IdVerification,
    Issuer,
    Language,
    LearningOutcome,
    Location,
    Mode,
    Note,
    PrimaryLanguage,
    ProvenBy,
    SpecifiedBy,
)
from platform_plugin_elm_credentials.api.utils import as_lang_string, get_fullname, to_iso_format


class CredentialBuilder:
    """
    Builds ELM credentials for a user based on a given course and certificate.

    This class provides a convenient way to construct ELM credentials for a user who has
    successfully completed a specified course and received a certificate of completion.

    Attributes:
        course_block (CourseBlock): The course for which credentials are being built.
        user (User): The user for whom credentials are being built.
        certificate (GeneratedCertificate): The certificate associated with the user's completion of the course.
        additional_params (dict): Additional parameters for the credential.
        elm_credential_defaults (dict): Default values for the credential.

    Properties:
        full_name (str): The full name of the user.
        language (Language): The language of the credential.
        primary_language (PrimaryLanguage): The primary language of the credential.
        org_country_code (CountryCode): The country code of the organisation in the credential.
        title (dict): The title of the credential.
        grade (Grade): The grade of the credential.
        issuer (Issuer): The issuer of the credential.

    Methods:
        get_maped_language() -> str:
            Get the language code mapped according to the language code defined.
        build() -> dict:
            Constructs and returns the ELM credential in the form of a dictionary.
    """

    LANGUAGE_CODE_MAP = {
        "en": "ENG",
        "es": "SPA",
    }
    LANGUAGE = "SPA"
    ORG_COUNTRY_CODE = "ESP"

    def __init__(self, course_block, user, certificate, additional_params):
        self.course_block = course_block
        self.user = user
        self.certificate = certificate
        self.additional_params = additional_params
        self.credential_settings = self.course_block.other_course_settings.get(
            "ELM_CREDENTIALS_DEFAULTS", {}
        ) or getattr(settings, "ELM_CREDENTIALS_DEFAULTS", {})

    @property
    def full_name(self) -> str:
        """
        Get the full name of the user.

        Returns:
            str: The full name of the user.
        """
        return self.user.profile.name

    @property
    def language(self) -> Language:
        """
        Get the language of the credential.

        Returns:
            Language: The language of the credential.
        """
        return Language(id=self.get_maped_language())

    @property
    def primary_language(self) -> PrimaryLanguage:
        """
        Get the primary language of the credential.

        Returns:
            PrimaryLanguage: The primary language of the credential.
        """
        return PrimaryLanguage(id=self.get_maped_language())

    @property
    def org_country_code(self) -> CountryCode:
        """
        Get the country code of the organisation in the credential.

        First, the country code is retrieved from the course settings. If it is not found,
        the primary language is retrieved from the Django setting. If it is not found,
        use the default country code.

        Returns:
            CountryCode: The country code of the credential.
        """
        org_country_code = self.credential_settings.get("org_country_code")
        return CountryCode(id=org_country_code or self.ORG_COUNTRY_CODE)

    @property
    def title(self) -> dict:
        """
        Get the title of the credential.

        Returns:
            str: The title of the credential.
        """
        return as_lang_string(
            f"Course certificate for passing {self.course_block.display_name} course"
        )

    @property
    def grade(self) -> Grade:
        """
        Get the grade of the credential.

        Returns:
            Grade: The grade of the credential.
        """
        note = str(round(float(self.certificate.grade) * 100, 2))
        return Grade(note_literal=as_lang_string(note))

    @property
    def issuer(self) -> Issuer:
        """
        Get the issuer of the credential.

        Returns:
            Issuer: The issuer of the credential.
        """
        issuer_id = self.credential_settings.get("issuer_id")
        return Issuer(
            id=issuer_id or str(uuid4()),
            alt_label=as_lang_string(self.course_block.org),
            legal_name=as_lang_string(self.course_block.org),
        )

    @property
    def learning_outcomes(self):
        """
        Get the learning outcomes (course topics) of the credential, if configured.

        Read from the ``topics`` key of ``ELM_CREDENTIALS_DEFAULTS``: a list of
        topic strings, e.g. ["Introduction to Python", "Version Control with Git"].

        Returns:
            list[LearningOutcome] | None: The learning outcomes, or None if not configured.
        """
        topics = self.credential_settings.get("topics")
        if not topics:
            return None
        return [
            LearningOutcome(
                id=f"urn:epass:learningOutcome:{index}",
                title=as_lang_string(topic),
            )
            for index, topic in enumerate(topics, start=1)
        ]

    @property
    def credit_points(self):
        """
        Get the credit points (e.g. ECTS) of the credential, if configured.

        Both ``credit_points`` (the numeric value, e.g. "5") and
        ``credit_framework_id`` (the EDC Controlled List of Educational Credit
        Systems concept id for the framework, e.g. the ECTS entry) must be set
        in ``ELM_CREDENTIALS_DEFAULTS`` for this to be included — there is no
        default framework id, since shipping an unverified one would be worse
        than omitting the property.

        Returns:
            list[CreditPoint] | None: The credit points, or None if not configured.
        """
        points = self.credential_settings.get("credit_points")
        framework_id = self.credential_settings.get("credit_framework_id")
        if not points or not framework_id:
            return None
        return [
            CreditPoint(
                id="urn:epass:creditPoint:1",
                framework={"id": framework_id, "type": "Concept"},
                point=str(points),
            )
        ]

    @property
    def additional_notes(self):
        """
        Get free-text additional notes for the credential, if configured.

        Currently used for the instructor name, read from the
        ``instructor_name`` key of ``ELM_CREDENTIALS_DEFAULTS``. ELM has no
        dedicated field for a named signatory (the electronic seal fulfils
        that role), so this is recorded as a plain note instead.

        Returns:
            list[Note] | None: The additional notes, or None if not configured.
        """
        instructor_name = self.credential_settings.get("instructor_name")
        if not instructor_name:
            return None
        return [
            Note(
                id="urn:epass:note:instructor:1",
                note_literal=as_lang_string(f"Instructor: {instructor_name}"),
            )
        ]

    def get_maped_language(self) -> str:
        """
        Get the language code mapped according to the language code defined.

        First, the language is retrieved from the course settings. If it is not found,
        the language is retrieved from the Django setting. If it is not found, use
        the default language.

        If you want to use a language code other than those in `LANGUAGE_CODE_MAP`, you can
        add a `language_map` dictionary to the `ELM_CREDENTIALS_DEFAULTS` setting.

        Returns:
            str: The language code
        """
        language_code = self.credential_settings.get("language_code")
        language_map = self.credential_settings.get("language_map", {})

        self.LANGUAGE_CODE_MAP.update(language_map)

        return language_code or self.LANGUAGE_CODE_MAP.get(
            getattr(settings, "LANGUAGE_CODE", "en"), self.LANGUAGE
        )

    def build(self) -> dict:
        """
        Build the credential.

        Returns:
            dict: The constructed ELM credential in dictionary format.
        """
        given_name, family_name = get_fullname(self.full_name)

        awarding_body = AwardingBody(
            alt_label=as_lang_string(self.course_block.org),
            legal_name=as_lang_string(self.course_block.org),
            location=[Location(address=[Address(country_code=self.org_country_code)])],
        )
        awarded_by = AwardedBy(
            awarding_body=[awarding_body],
            awarding_date=to_iso_format(self.certificate.created_date),
        )
        specified_by = SpecifiedBy(
            title=self.title,
            language=self.language,
            mode=Mode(),
            learning_outcome=self.learning_outcomes,
            credit_point=self.credit_points,
            additional_note=self.additional_notes,
        )
        proven_by = ProvenBy(
            awarded_by=awarded_by,
            title=self.title,
            grade=self.grade,
            id_verification=IdVerification(),
        )
        has_claim = HasClaim(
            proven_by=proven_by,
            awarded_by=awarded_by,
            title=self.title,
            specified_by=specified_by,
        )
        credential_subject = CredentialSubject(
            given_name=as_lang_string(given_name),
            family_name=as_lang_string(family_name),
            full_name=as_lang_string(self.full_name),
            has_claim=[has_claim],
        )
        display_parameter = DisplayParameter(
            primary_language=self.primary_language,
            language=[self.language],
            title=as_lang_string(self.course_block.display_name),
        )
        delivery_details = DeliveryDetails(delivery_address=[self.user.email])

        return {
            "credential": {
                "issuer": self.issuer,
                "credential_subject": credential_subject,
                "expiration_date": self.additional_params.get("expires_at"),
                "valid_until": self.additional_params.get("expires_at"),
                "display_parameter": display_parameter,
            },
            "delivery_details": delivery_details,
        }
