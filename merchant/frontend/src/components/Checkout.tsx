import React, { useState } from "react";

import { Button, Col, Row, UncontrolledTooltip } from "reactstrap";
import QRCode from "qrcode.react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faQuestionCircle } from "@fortawesome/free-solid-svg-icons";
import { fiatToHumanFriendly } from "utils";
import "../assets/scss/pay-with-stable.css";
import { WalletLink } from "services/merchant";

export interface CheckoutProps {
  paymentId: string;
  orderId: string;
  demoMode: boolean;
  qr: string;
  deepLink: string;
  walletLinks: WalletLink[];
  fiatPrice: number;
  fiatCurrency: string;
}

export default function Checkout({
  deepLink,
  fiatPrice,
  fiatCurrency,
  walletLinks,
  demoMode,
}: CheckoutProps) {
  const [chooseWallet, setChooseWallet] = useState(true);

  const handleClick = () => {
    setChooseWallet(false);
  };

  return (
    <>
      <div className="w-100">
        <Row>
          <Col className="text-nowrap text-right">Total price:</Col>
          <Col className="d-flex align-items-center">
            <span className="text-nowrap">
              {fiatToHumanFriendly(fiatPrice)} {fiatCurrency}
            </span>
            <FontAwesomeIcon
              size="xs"
              icon={faQuestionCircle}
              className="ml-2"
              id="totalPriceHelp"
            />
            <UncontrolledTooltip target="totalPriceHelp">
              The price in fiat set by the merchant
            </UncontrolledTooltip>
          </Col>
        </Row>
      </div>
      <div>
        {!chooseWallet ? (
          <>
            <QRCode
              className="img-fluid mt-4"
              size={192}
              value={deepLink}
              imageSettings={{
                src: require("../logo.svg"),
                height: 32,
                width: 32,
                excavate: true,
              }}
            />
            <div className="text-center small py-4 font-weight-bold">
              - OR -
            </div>
            <div className="text-center">
              <Button
                color="primary"
                size="sm"
                onClick={() => setChooseWallet(true)}
              >
                Open in wallet
              </Button>
            </div>
          </>
        ) : (
          <>
            <div className="mt-4">
              <div className="text-center">Choose your wallet:</div>
              <div className="pay-with-stable">
                <div className="payment-options">
                  <div className="">
                    {walletLinks.map((option) => (
                      <div className="mt-4" key={option.walletName}>
                        <a
                          className="btn btn-block btn-primary text-left"
                          href={option.link}
                        >
                          <img
                            src={option.logo.image}
                            alt={option.logo.alt}
                            height={32}
                          />{" "}
                          {option.walletName}
                        </a>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
            <div className="text-center small py-4 font-weight-bold">
              - OR -
            </div>
            <div className="text-center">
              <Button color="primary" size="sm" onClick={() => handleClick()}>
                Scan QR
              </Button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
