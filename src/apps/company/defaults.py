"""
Default company-profile values.

HOZA_* hold the exact identity, terms and bank details that were hardcoded
before Company Settings existed. The seed migration copies them into the
first CompanyProfile so existing documents stay word-for-word identical;
GENERIC_* are what a brand-new company starts from.
"""

# Sales agreement terms: one clause per line.
HOZA_TERMS_ENGLISH = '\n'.join([
    '1. That the purchaser shall take possession of the motor vehicle immediately upon signing this agreement',
    "2. The motor vehicle sold on 'AS IT IS' and where it is basis and the purchase has taken possession upon being satisfied that same is in proper and sound mechanical, type and body condition",
    '3. This is used vehicle the vendor does not give the purchaser any guarantee or warranty whatsoever as to the worthiness of the motor vehicle and no CLAIM on this account shall be entertained',
    '4. That the COMMITMENT paid herein by the purchaser shall not be refundable in full amount. The fee shall attract a penalty of 60% upon refunding the amount. The minimum commitment fee therefore shall be Kshs.50,000',
    '5. The vendor shall be at liberty to repossess the motor vehicle without any further notice in the event the purchaser defaults in paying any of the remaining balance as agreed and in such a case the purchaser shall meet all the repossess and incidental charges and further, the buyer shall pay the seller a further sum equivalent to 20% MONTHLY of the remain balance as penalty for the default.',
    '6. THAT on repossession of the vehicle the total outstanding balance shall fail due and owing the same shall have to be paid in full within 15 days from the date of such repossession FAILURE to which the vendor shall have the right to sell the motor vehicle to recover the outstanding balance.',
    '7. The purchaser shall not sell the vehicle to a third party or remove it out of Kenya before paying the vendor in full and or change the road license(s) or route without permission and prior notification of the vendor.',
    "8. THAT upon taking possession of the motor vehicle the purchaser shall take an insurance cover as well as the CAR TRACK GADGET if required in case of settling remaining amount of the total price of the car as agreed and this shall be fully facilitated by HOZA Investment (K) Limited via its company's broker and the purchaser should solemnly settle agreeable insurance fee and car track fee. Furthermore, should the motor vehicle be involved in an accident or stolen it shall be the sole responsibility of the purchaser notwithstanding the fact that motor vehicle has not been formally transferred into its/his/her name.",
    '9. THAT the purchaser after acquiring the vehicle has no authority whatsoever to dismantle tracker gadget or any serious mechanical or electric modification without the consent of the vendor.',
    '10. In case the purchaser make any cheques in favour of the vendor for purchase price or any part thereof, the purchaser hereby expressly warrants that there will be sufficient fund on his/her/its account when the said cheque [s] is presented for payment and that in the case of the dishonor of the cheque[s] then the purchaser hereby undertakes liability on the said cheque [s] both in the civil and criminal liability.',
    '11. Upon completion of the purchase price the purchaser is required to pay a transfer fee, and in the case of commercial vehicle pay inspection fee, booking fee, advance tax fee among other fees that are mandatory. Therefore he/she/its should issue pin/ID copies or certificates of registration & required documents for transfer of the log book before it is issued by the vendor to the purchaser.',
])

HOZA_TERMS_SWAHILI = '\n'.join([
    '1. Mnunuzi atamiliki gari pindi atakapo tia sahihi kwenye karatasi ya makubaliano',
    "2. Mteja anakubali kununua gari kwa njia ya 'JINSI ILIVYO' na anaridhika kununua kwamba amekubali jinsi ilivyo hali ya kiufundi na muundo",
    '3. Gari hii imetumika na mnunuzi hapewi udhamini wowote wa gari na hakuna lawama yeyote inakubaliwa baada ya kununua gari',
    '4. Pesa iliyolipwa na mnunuzi kama rubuni hairudishwi kwa njia yeyote ila itapunguzwa kwa asili mia sitini [60%] kisha iliyosalia apewe mnunuzi baada ya kujieleza kuhusu kuihairisha shughuli ya kununua gari. Malipo ya rubuni itakuwa kiasi cha 50,000 elfu.',
    '5. Muuzaji anaruhusiwa kuchukua tena gari baada ya mnunuzi kushindwa kulipa malipo yaliyosalia hivyo basi mnunuzi atagharamikia gharama zote za kuchukua ile gari kutoka kwake hadi kwa muuzaji. Mnunuzi atakaposhindwa kulipa pesa kwa muda uliowekwa atamlipa muuzaji pesa zaidi kwa asilimia 20% kila MWEZI ya pesa waliokuwa wamekubaliana kama faini kwa kutotimiza mkataba.',
    '6. Baada ya muuzaji kuchukua ile gari, pesa iliyobakia inatakiwa kulipwa kabla ya siku kumi na mitano (15) na isipolipwa katikati ya huo muda muuzaji anaruhusiwa kuuza gari tena ili apate pesa hizo.',
    '7. Mnunuzi haruhusiwi kuuza ile gari kwa mtu mwingine au kuitoa nje ya Kenya kabla hajalipa muuzaji pesa yote au kubadilisha leseni ya barabara bila idhini ya mwenye gari.',
    '8. Baada ya kumiliki gari, mnunuzi atachukua jukumu ya kulipia bima ya gari na itakuwa mpangilio wa Kampuni ya HOZA Investment (K) Limited itakayo muezesha mnunuzi kupata bima ya namna ilivyo jadiliwa kwa kumhusisha kampuni ya udalali inayoshughulikia maswala ya bima na hata pia shughuli ya mtambo wa kitegesho na kuchunguza muenendo ya gari iwapo mnunuzi atabakisha sehemu ya jumla ya bei ya gari kwa njia ya mkopo na gari kwa namna yeyote ipate ajali ama kuibiwa basi ni jukumu la mnunuzi kuijishughulisha bila ya kumhusisha na kumlaumu muuzaji gari kwa njia yoyote ile.',
    '9. Mnunuzi baada ya kununua gari haswa kwa njia ya mkopo, hastahili kwa namna yeyote ile kuharibu ama kutoa mtambo wa kiegesho ama wa kuchunguza muenendo wa gari na kadhalika bila idhini ya muuzaji.',
    '10. Kama mnunuzi atapeana cheki kwa muuzaji, inaamanisha kuwa mnunuzi yuko na uhakika kwamba katika akaunti yake ya benki ina pesa za kutosha na wakati wa kupeleka hiyo cheki kwenye benki, akaunti yake itakua na pesa pia inaamanisha mnunuzi amechukua huo wadhifa kisheria.',
    '11. Baada ya kulipa pesa zote za kununua gari mnunuzi anahitajika kulipa pesa ya kuhamisha usajili wa gari kwa majina yake, anastahili pia kulipia shughuli za kufanyia gari ukaguzi na shughuli zingine zenye umuhimu za kukamilika pia anafaa kupeana nakala ya pin/kitambulisho na kartasi zote zinazohitajika kwa ajili ya kumiliki logbook kwa majina yake.',
])

GENERIC_TERMS_ENGLISH = '\n'.join([
    '1. That the purchaser shall take possession of the motor vehicle immediately upon signing this agreement',
    "2. The motor vehicle is sold on 'AS IT IS' and where it is basis, and the purchaser has taken possession upon being satisfied that it is in proper and sound mechanical and body condition",
    '3. This is a used vehicle; the vendor gives the purchaser no guarantee or warranty whatsoever as to the worthiness of the motor vehicle',
    '4. The vendor shall be at liberty to repossess the motor vehicle without further notice if the purchaser defaults in paying any of the remaining balance as agreed',
    '5. The purchaser shall not sell the vehicle to a third party before paying the vendor in full',
    '6. Upon completion of the purchase price the purchaser shall pay the transfer fee and any other statutory fees',
])

# Bank accounts printed on proforma invoices (previously
# ProformaInvoice.COMPANY_ACCOUNTS), keyed by the legacy proforma choice code.
HOZA_BANK_ACCOUNTS = {
    'equity': {
        'payment_method_code': 'equity_hoza',
        'bank': 'Equity Bank',
        'branch': 'Moi Avenue Branch, Mombasa',
        'account_name': 'HOZA INVESTMENT (K) LIMITED',
        'account_number': '0250279299771',
    },
    'dib': {
        'payment_method_code': 'dib_hoza',
        'bank': 'DIB (Dubai Islamic Bank)',
        'branch': 'Kilindini Branch, Mombasa',
        'account_name': 'HOZA INVESTMENT K LIMITED',
        'account_number': '003505100422901',
    },
    'coop': {
        'payment_method_code': 'coop_hoza',
        'bank': 'Co-operative Bank of Kenya',
        'branch': 'Nkrumah Road Branch, Mombasa',
        'account_name': 'Hoza Investment K Limited',
        'account_number': '01192447998000',
    },
}
