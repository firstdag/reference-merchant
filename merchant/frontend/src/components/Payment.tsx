import React, { useEffect, useState } from "react";
import { Modal, ModalBody, ModalHeader, Spinner } from "reactstrap";
import BackendClient, { PaymentProcessingDetails } from "../services/merchant";
import { Product } from "../interfaces/product";
import Checkout from "./Checkout";

export interface PaymentProps {
  product?: Product;
  isOpen: boolean;
  demoMode: boolean;
  onClose: () => void;
}

export default function Payment({
  product,
  isOpen,
  demoMode,
  onClose,
}: PaymentProps) {
  const [paymentProcessingDetails, setPaymentProcessingDetails] = useState<
    PaymentProcessingDetails | undefined
  >();
  type PaymentState =
    | "inactive"
    | "fetchingProcessingDetails"
    | "paying"
    | "paymentCleared";
  const [paymentState, setPaymentState] = useState<PaymentState>("inactive");

  if (paymentState === "inactive" && isOpen && !!product) {
    setPaymentState("fetchingProcessingDetails");
  }

  // Initiates payment
  useEffect(() => {
    let isOutdated = false;

    const fetchPaymentDetails = async () => {
      try {
        if (paymentState !== "fetchingProcessingDetails") return;

        const payment = await new BackendClient().checkoutOne(product!.gtin);

        if (!isOutdated) {
          setPaymentProcessingDetails(payment);
          setPaymentState("paying");
        }
      } catch (e) {
        console.error("Unexpected error", e);
      }
    };

    // noinspection JSIgnoredPromiseFromCall
    fetchPaymentDetails();

    return () => {
      isOutdated = true;
    };
  }, [paymentState, product]);

  const onModalClosed = () => {
    setPaymentState("inactive");
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      centered={true}
      size="md"
      toggle={onModalClosed}
      fade={true}
    >
      <ModalHeader toggle={onModalClosed}>{product?.name}</ModalHeader>
      <ModalBody className="p-0">
        {paymentState === "fetchingProcessingDetails" && (
          <div className="d-flex justify-content-center my-5">
            <Spinner color="primary" />
          </div>
        )}

        {paymentState === "paying" && (
          <Checkout
            paymentId={paymentProcessingDetails!.orderId}
            orderId={paymentProcessingDetails!.orderId}
            demoMode={false}
            qr={paymentProcessingDetails!.qr}
            deepLink={paymentProcessingDetails!.deepLink}
            walletLinks={paymentProcessingDetails!.walletLinks}
            fiatPrice={product!.price}
            fiatCurrency={product!.currency}
          />
        )}

        {paymentState === "paymentCleared" && (
          <h4 className="my-5 text-success text-center">
            <i className="fa fa-check" /> Paid successfully!
          </h4>
        )}
      </ModalBody>
    </Modal>
  );
}
