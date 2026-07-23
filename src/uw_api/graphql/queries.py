from __future__ import annotations

GET_ACCOUNT = """\
query GetAccount {
  account {
    id
    number
    __typename
  }
}"""

GET_ACCOUNT_DETAILS = """\
query AccountDetails {
  account {
    details {
      ... on ResidentialDetails {
        isStaff
        __typename
      }
      ... on BusinessDetails {
        businessName
        __typename
      }
      ... on LegacyBusinessDetails {
        isStaff
        __typename
      }
      __typename
    }
    __typename
  }
}"""

GET_LIVE_SERVICES = """\
query GetLiveServices($accountId: String!) {
  getDashboardServices(accountID: $accountId) {
    broadband { services { status __typename } __typename }
    energy { services { status __typename } __typename }
    insurance { services { status __typename } __typename }
    mobile { services { status __typename } __typename }
    __typename
  }
}"""

GET_BALANCE = """\
query Balance($id: String!) {
  finance {
    account(id: $id) {
      overdueBalance { value __typename }
      dueBalance { value __typename }
      __typename
    }
    __typename
  }
}"""

GET_OVERDUE_BALANCE = """\
query OverdueBalance($id: String!) {
  finance {
    account(id: $id) {
      id
      overdueBalance { value currency showNotification __typename }
      __typename
    }
    __typename
  }
}"""

GET_PAYMENT_METHOD = """\
query GetPaymentMethod {
  customerBilling {
    paymentDetails { paymentMethod __typename }
    __typename
  }
}"""

GET_BILLS = """\
query GetBills {
  customerBilling {
    id
    accountBills {
      billsList {
        invoiceId
        invoiceDate { seconds nanos __typename }
        total { value currency __typename }
        url
        __typename
      }
      __typename
    }
    __typename
  }
}"""

GET_PDF_URL = """\
query GetPdfUrl($month: Int!, $year: Int!) {
  customerBilling {
    pdfUrl(input: {month: $month, year: $year})
    __typename
  }
}"""

GET_ENERGY_SERVICES = """\
query accountEnergyServicesWithReads($includeEndedWithin: Int) {
  account {
    id
    energy {
      services(input: {includeEndedWithin: $includeEndedWithin}) {
        ...ReadsJourneyEnergyService
        __typename
      }
      __typename
    }
    __typename
  }
}

fragment ReadsJourneyEnergyService on EnergyService {
  id
  fuelType
  reference
  isLive
  serviceState
  endDateTime
  startDateTime
  meterpoint {
    installedMeter {
      ...Meter
      __typename
    }
    site {
      id
      address { ...Address __typename }
      __typename
    }
    __typename
  }
  __typename
}

fragment Meter on EnergyMeter {
  id
  isSmart
  isResponsive
  serialNumber
  registers { id label dials __typename }
  reads {
    latestRead { ...MeterRead __typename }
    latestActualRead: latestRead(input: {excludeEstimated: true}) {
      ...MeterRead __typename
    }
    __typename
  }
  __typename
}

fragment MeterRead on EnergyMeterRead {
  id
  isEstimated
  isSuppressed
  readDate
  registerReading { label registerId value __typename }
  source
  state
  __typename
}

fragment Address on SiteAddress {
  uprn
  subBuildingNameNumber
  buildingNameNumber
  dependentThoroughfare
  thoroughfare
  dependentLocality
  doubleDependentLocality
  locality
  town
  postcode
  county
  department
  poBox
  organisation
  deliveryPointSuffix
  __typename
}"""

GET_READ_HISTORY = """\
query accountReadHistory($input: MeterReadsHistoryInput) {
  account {
    energy {
      services {
        id
        reference
        meterpoint {
          installedMeter {
            reads {
              history(input: $input) {
                totalCount
                reads { ...MeterRead __typename }
                __typename
              }
              __typename
            }
            __typename
          }
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}

fragment MeterRead on EnergyMeterRead {
  id
  isEstimated
  isSuppressed
  readDate
  registerReading { label registerId value __typename }
  source
  state
  __typename
}"""

GET_EV_TARIFF = """\
query accountServicesEvTariff {
  account {
    id
    energy {
      services {
        energyTariff { isElectricVehicleTariff __typename }
        __typename
      }
      __typename
    }
    __typename
  }
}"""
